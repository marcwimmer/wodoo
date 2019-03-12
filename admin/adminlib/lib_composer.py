from copy import deepcopy
import subprocess
import time
import inquirer
import importlib
import re
import yaml
from datetime import datetime
import sys
import shutil
import hashlib
import os
import tempfile
import copy
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __replace_in_file
from .tools import __safe_filename
from .tools import _file2env
from .tools import __file_get_lines
from .tools import __empty_dir
from .tools import __find_files
from .tools import _get_platform
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from .tools import _remove_temp_directories
from .tools import __makedirs
from .tools import _prepare_filesystem
from .tools import __rmtree
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def composer(config):
    pass

@composer.command(name='reload')
@click.pass_context
def do_reload(ctx):
    """
    After settings change call this def to update all settings.
    """
    from . import MyConfigParser
    config = MyConfigParser(files['settings'])
    ctx.invoke(do_compose, customs=config['CUSTOMS'], db=config['DBNAME'], demo=config['ODOO_DEMO'] == "1")

@composer.command(name="compose")
@click.argument("customs", required=True)
@click.argument("db", required=False)
@click.option("--demo", is_flag=True, help="Enabled demo data.")
@pass_config
def do_compose(config, customs='', db='', demo=False):
    """
    builds docker compose, proxy settings, setups odoo instances
    """
    from . import MyConfigParser

    def setup_settings_file():
        """
        Cleans run/settings and sets minimal settings;
        Puts default values in settings.d to override any values
        """
        config = MyConfigParser(files['settings'])
        if customs:
            if config.get('CUSTOMS', '') != customs:
                config.clear()
                config['CUSTOMS'] = customs
                config.write()
        vals = {}
        if customs:
            vals['CUSTOMS'] = customs
        vals['DBNAME'] = db or customs
        if demo:
            vals['ODOO_DEMO'] = "1" if demo else "0"

        for k, v in vals.items():
            if config.get(k, '') != v:
                config[k] = v
                config.write()
        if not os.path.isdir(dirs['settings.d']):
            os.makedirs(dirs['settings.d'])
        config_compose_minimum = MyConfigParser(os.path.join(dirs['settings.d'], 'compose'))
        config_compose_minimum.clear()
        for k in ['CUSTOMS', 'DBNAME', 'ODOO_DEMO']:
            if k in vals:
                config_compose_minimum[k] = vals[k]
        config_compose_minimum.write()
    setup_settings_file()

    _export_settings(customs)
    _remove_temp_directories()
    _prepare_filesystem()
    _prepare_yml_files_from_template_files(config)
    _reset_proxy_configs()
    _setup_proxy(config)
    _setup_odoo_instances(config)
    # ln path ./src to customs
    SRC_PATH = os.path.join(os.environ['LOCAL_ODOO_HOME'], 'src')
    if os.path.islink(SRC_PATH):
        os.unlink(SRC_PATH)
    os.symlink('data/src/customs/{}'.format(config.customs), SRC_PATH)

    click.echo("Built the docker-compose file.")

def _prepare_yml_files_from_template_files(config):
    # replace params in configuration file
    # replace variables in docker-compose;
    from . import odoo_config

    # python: find all configuration files from machines folder; extract sort
    # by manage-sort flag and put file into run directory
    # only if RUN_parentpath like RUN_ODOO is <> 0 include the machine
    #
    # - also replace all environment variables
    def find_files(dir, recursive=True):
        cmd = [
            dir,
        ]
        if not recursive:
            cmd += ['-maxdepth', '1']

        cmd += [
            '-regex',
            r'.*\/docker-compose.*.yml',
        ]
        for filepath in __find_files(*cmd):
            yield filepath
    _files = []
    _files += find_files(dirs['machines'])
    _files += find_files(odoo_config.customs_dir())
    for d in [
        os.path.join('/etc_host/odoo'),
        os.path.join('/etc_host/odoo', config.customs),
    ]:
        if os.path.exists(d):
            _files += find_files(d, recursive=False)

    _prepare_docker_compose_files(config, files['docker_compose'], _files)

def _reset_proxy_configs():
    __empty_dir(dirs['run/proxy'])

def __replace_all_envs_in_str(content, env):
    """
    Docker does not allow to replace volume names or service names, so we do it by hand
    """
    all_params = re.findall(r'\$\{[^\}]*?\}', content)
    for param in all_params:
        name = param
        name = name.replace("${", "")
        name = name.replace("}", "")
        if name in env.keys():
            content = content.replace(param, env[name])
    return content

def _prepare_docker_compose_files(config, dest_file, paths):
    from . import YAML_VERSION
    from . import MyConfigParser
    local_odoo_home = os.environ['LOCAL_ODOO_HOME']

    final_contents = []

    if not dest_file:
        raise Exception('require destination path')

    with open(dest_file, 'w') as f:
        f.write("#Composed {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("version: '{}'\n".format(config.compose_version))
    myconfig = MyConfigParser(files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # add static yaml content to each machine
    with open(files['config/default_network'], 'r') as f:
        default_network = yaml.load(f.read())

    for path in paths:
        with open(path, 'r') as f:
            content = f.read()
        filename = os.path.basename(path)

        def use_file():
            if "run_odoo_version.{}.yml".format(config.odoo_version) in filename:
                return True
            if 'run_' in filename:
                run = re.findall(r'run_[^\.]*', filename)
                if run:
                    if '!run' in filename:
                        if not getattr(config, run[0]):
                            return True
                    else:
                        if getattr(config, run[0]):
                            return True
                return False
            else:
                return True

        if not use_file():
            continue

        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
        order = int(order)
        folder_name = os.path.basename(os.path.dirname(path))

        if '.run_' not in path:
            if not getattr(config, "run_{}".format(folder_name)):
                continue

        j = yaml.load(content)
        if j:
            # TODO complain version - override version
            j['version'] = YAML_VERSION

            # set settings environment and the override settings after that
            for file in ['run/settings']:
                path = os.path.join(local_odoo_home, file)
                if os.path.exists(path):
                    if 'services' in j:
                        for service in j['services']:
                            service = j['services'][service]
                            if 'env_file' not in service:
                                service['env_file'] = []
                            if isinstance(service['env_file'], str):
                                service['env_file'] = [service['env_file']]

                            if not [x for x in service['env_file'] if x == '$ODOO_HOME/{}'.format(file)]:
                                service['env_file'].append('$ODOO_HOME/{}'.format(file))
                j['networks'] = copy.deepcopy(default_network['networks'])

            content = yaml.dump(j, default_flow_style=False)
        content = __replace_all_envs_in_str(content, env)

        final_contents.append((order, content))

    def post_process_complete_yaml_config(yml):
        """
        This is after calling docker-compose config, which returns the
        complete configuration.

        Aim is to take the volumes defined in odoo_base and append them
        to all odoo containers.
        """

        with open(os.path.join(local_odoo_home, 'machines/odoo/docker-compose.yml')) as f:
            odoodc = yaml.load(f.read())

        for odoomachine in odoodc['services']:
            if odoomachine == 'odoo_base':
                continue
            if odoomachine not in yml['services']:
                continue
            machine = yml['services'][odoomachine]
            for k in ['volumes']:
                machine[k] = []
                for x in yml['services']['odoo_base'][k]:
                    machine[k].append(x)
            for k in ['environment']:
                machine.setdefault(k, {})
                if 'odoo_base' in yml['services']:
                    for x, v in yml['services']['odoo_base'][k].items():
                        machine[k][x] = v
        if 'odoo_base' in yml['services']:
            yml['services'].pop('odoo_base')
        yml['version'] = YAML_VERSION

        # remove restart policies, if not restart allowed:
        if not config.restart_containers:
            for service in yml['services']:
                # TODO CLEANUP -> more generic instructions ...
                if 'restart' in yml['services'][service] or \
                        (service == 'odoo_cronjobs' and not config.run_odoo_cronjobs) or \
                        (service == 'proxy' and not config.run_proxy):
                    yml['services'][service].pop('restart')

        return yml

    # call docker compose config to get the complete config
    final_contents.sort(key=lambda x: x[0])

    temp_path = os.path.join(local_odoo_home, '.tmp.compose')
    if os.path.isdir(temp_path):
        shutil.rmtree(temp_path)
    os.makedirs(temp_path)
    try:
        temp_files = []
        for i, filecontent in enumerate(final_contents):
            path = os.path.join(temp_path, str(i).zfill(10) + '.yml')
            with open(path, 'w') as f:
                f.write(filecontent[1])
                f.flush()
            temp_files.append("-f")
            temp_files.append(os.path.basename(path))

        cmdline = []
        cmdline.append("/usr/local/bin/docker-compose")
        cmdline += temp_files
        cmdline.append('config')

        d = deepcopy(os.environ)
        d.update(env)
        conf = __system(cmdline, cwd=temp_path, env=d)
        # post-process config config
        conf = post_process_complete_yaml_config(yaml.load(conf))
        conf = yaml.dump(conf, default_flow_style=False)

        with open(dest_file, 'w') as f:
            f.write(conf)
    finally:
        shutil.rmtree(temp_path)

def _setup_proxy(config):
    from . import odoo_config
    from . import MyConfigParser
    CONFIG_DIR = dirs['run/proxy']
    __empty_dir(dirs['proxy_configs_dir'])

    sys.path.append(dirs['machines/proxy'])
    importlib.import_module("add_upstream")
    from add_upstream import add_upstream as f_add_upstream

    def get_rules():
        for root, _, _filenames in os.walk(dirs['machines']):
            for filename in _filenames:
                if filename == 'upstream.path':
                    filepath = os.path.join(root, filename)
                    machine = None
                    p = filepath
                    while os.path.basename(p) != "machines":
                        machine = os.path.basename(p)
                        p = os.path.dirname(p)
                    del p

                    try:
                        version = float(os.path.basename(os.path.dirname(filepath)))
                    except Exception:
                        version = None
                    else:
                        if str(version) != str(odoo_config.get_version_from_customs(config.customs)):
                            continue
                    with open(filepath, 'r') as f:
                        content = f.readlines()
                        for line in content:
                            LOCATION, UPSTREAM = line.strip().split(" ")
                            if not LOCATION or not UPSTREAM:
                                raise Exception("Invalid rule: {}".format(line))
                            yield filepath, LOCATION, UPSTREAM, machine

    for filepath, LOCATION, UPSTREAM, machine in get_rules():
        __makedirs(os.path.join(CONFIG_DIR, machine))
        location_friendly_name = LOCATION.replace("/", "_")
        filename = "{}.location".format(location_friendly_name)
        CONFIG_PATH = os.path.join(CONFIG_DIR, machine, filename)
        UPSTREAM_INSTANCE = UPSTREAM.replace("default", "odoo")
        f_add_upstream(LOCATION, UPSTREAM_INSTANCE, CONFIG_PATH)

def _setup_odoo_instances(config):
    def __add_location_files(config_path, dir):
        lines = []
        for subdir in os.listdir(dir):
            if os.path.isdir(os.path.join(dir, subdir)):
                for file in os.listdir(os.path.join(dir, subdir)):
                    lines.append("\tInclude " + os.path.join("/etc/proxy", os.path.basename(subdir), file))
        __replace_in_file(config_path, "__INCLUDES__", '\n'.join(lines))

    if os.path.exists(files['odoo_instances']):

        if os.path.exists(files['odoo_instances']):
            for line in __file_get_lines(files['odoo_instances']):
                name, domain = line.strip().split(" ")
                config_path = os.path.join(dirs['proxy_configs_dir'], "{}.host".format(name))
                shutil.copy(files['machines/proxy/instance.conf'], config_path)

                if domain == "default":
                    __replace_in_file(config_path, "__DOMAIN__", '*')
                else:
                    if domain:
                        __replace_in_file(config_path, "__DOMAIN__", domain)
                if name != "default":
                    # adapt the one yml file and duplicate the odoo service there;
                    # removing any ports
                    with open(files['docker_compose']) as f:
                        j = yaml.load(f.read())
                    odoo = copy.deepcopy(j['services']['odoo'])
                    if 'ports' in odoo:
                        del odoo['ports']
                    odoo['container_name'] = '_'.join([config.CUSTOMS, "odoo", name])
                    j['services']['odoo_{}'.format(name)] = odoo
                    with open(files['docker_compose'], 'w', 0) as f:
                        f.write(yaml.dump(j, default_flow_style=False))

    for file in os.listdir(dirs['run/proxy']):
        if not file.endswith('.host'):
            continue
        config_path = os.path.join(dirs['run/proxy'], file)
        __add_location_files(config_path, dirs['run/proxy'])

def _export_settings(customs):
    from . import files
    from . import odoo_config
    from . import MyConfigParser

    if not os.path.exists(files['settings']):
        raise Exception("Please call ./odoo compose <CUSTOMS> initially.")

    setting_files = _collect_settings_files(customs)
    _make_settings_file(files['settings'], setting_files)
    fileconfig = MyConfigParser(files['settings'])

    __postprocess_config(fileconfig)
    # store the host root folder
    # fileconfig['HOST_ODOO_HOME'] = config.odoo_home
    fileconfig.write()

def _collect_settings_files(customs):
    from . import dirs
    _files = []
    _files.append(os.path.join(dirs['odoo_home'], 'machines/defaults'))
    # optimize
    for filename in __find_files(dirs['machines'], "-name", "default.settings"):
        _files.append(os.path.join(dirs['machines'], filename))

    for dir in _get_settings_directories(customs):
        if os.path.isfile(dir):
            _files.append(dir)
        elif os.path.isdir(dir):
            for filename in os.listdir(dir):
                _files.append(os.path.join(dir, filename))
    return _files

def _make_settings_file(outfile, setting_files):
    """
    Puts all settings into one settings file
    """
    from . import PLATFORM_OSX
    from . import MyConfigParser
    c = MyConfigParser(outfile)
    for file in setting_files:
        if not file:
            continue
        c2 = MyConfigParser(file)

        for key in c2.keys():
            value = c2[key]
            if '~' in value:
                value = value.replace('~', os.environ['HOST_HOME'])
                c2[key] = value

        c.apply(c2)

    if _get_platform() == PLATFORM_OSX:
        c['RUN_RSYNCED'] = '1'
    c.write()

def _get_settings_directories(customs):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    from . import dirs
    customs_dir = odoo_config.customs_dir(customs)
    yield os.path.join(customs_dir, 'settings')
    if os.path.exists('/etc_host/odoo/{}/settings'.format(customs)):
        yield '/etc_host/odoo/{}/settings'.format(customs)
    if os.path.exists('/etc_host/odoo/settings'):
        yield '/etc_host/odoo/settings'
    yield dirs['settings.d']

def __postprocess_config(config):
    """
    keep if xxx in config queries for the toggle command. It sets
    a sub config file which does not contain all keys.
    """
    from . import odoo_config
    if "CUSTOMS" in config.keys():
        config['ODOO_VERSION'] = str(float(odoo_config.get_version_from_customs(config['CUSTOMS'])))
        config['HOST_ODOO_HOME'] = os.getenv("HOST_ODOO_HOME")

    if 'RUN_POSTGRES' in config.keys() and config['RUN_POSTGRES'] == '1':
        default_values = {
            "DB_HOST": "postgres",
            "DB_PORT": "5432",
            "DB_USER": "odoo",
            "DB_PWD": "odoo"
        }
        for k, v in default_values.items():
            if config.get(k, "") != v:
                config[k] = v

    if "RUN_POSTGRES" in config.keys() and config.get("RUN_POSTGRES", "") != "1" and config.get("RUN_POSTGRES_IN_RAM", "") == "1":
        config['RUN_POSTGRES_IN_RAM'] = "1"

    if "DEVMODE" in config.keys() and config.get("DEVMODE", "0") == "1":
        config['RUN_ODOODEV'] = "1"
    else:
        config['RUN_ODOODEV'] = "0"

    if "RUN_CALENDAR" in config.keys() and config.get("RUN_CALENDAR", "") == "1":
        config['RUN_CALENDAR_DB'] = "1"

@composer.command(name='toggle-settings')
@pass_config
@click.pass_context
def toggle_settings(ctx, config):
    from . import MyConfigParser
    myconfig = MyConfigParser(files['settings'])
    config_local = MyConfigParser(files['settings_local'])

    choices = [
        "DEVMODE",
    ]
    default = []

    for key in sorted(myconfig.keys()):
        if key.startswith("RUN_"):
            choices.append(key)

    for choice in choices:
        if myconfig[choice] == '1':
            default.append(choice)

    questions = [
        inquirer.Checkbox(
            'run',
            message="What services to run? {}/{}".format(config.customs, config.dbname),
            choices=choices,
            default=default,
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers:
        return
    for option in choices:
        config_local[option] = '1' if option in answers['run'] else '0'
    __postprocess_config(config_local)
    config_local.write()
    Commands.invoke(ctx, 'reload')


Commands.register(do_reload, 'reload')
Commands.register(do_compose, 'compose')
