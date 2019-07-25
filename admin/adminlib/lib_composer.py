from pathlib import Path
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
from .tools import __running_as_root_or_sudo
from .tools import __assert_file_exists
from .tools import __system
from .tools import __replace_in_file
from .tools import __safe_filename
from .tools import _file2env
from .tools import __file_get_lines
from .tools import __empty_dir
from .tools import _get_platform
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
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
        dirs['settings.d'].mkdir(parents=True, exist_ok=True)
        config_compose_minimum = MyConfigParser(dirs['settings.d'] / 'compose')
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
    _setup_odoo_instances(config)
    # ln path ./src to customs
    SRC_PATH = Path(os.environ['LOCAL_ODOO_HOME']) / 'src'
    if SRC_PATH.is_symlink():
        SRC_PATH.unlink()
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
    _files = []
    for dir in [
        dirs['machines'],
        odoo_config.customs_dir(),
    ]:
        [_files.append(x) for x in dir.glob("**/docker-compose*.yml")]
    for d in [
        Path('/etc_host/odoo'),
        Path('/etc_host/odoo') / config.customs,
    ]:
        if d.exists():
            [_files.append(x) for x in d.glob("docker-compose*.yml")] # not recursive

    _prepare_docker_compose_files(config, files['docker_compose'], _files)

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
    local_odoo_home = Path(os.environ['LOCAL_ODOO_HOME'])

    final_contents = []

    if not dest_file:
        raise Exception('require destination path')

    with dest_file.open('w') as f:
        f.write("#Composed {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("version: '{}'\n".format(config.compose_version))
    myconfig = MyConfigParser(files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))
    env['ODOO_HOME'] = os.environ["HOST_ODOO_HOME"]

    # add static yaml content to each machine
    with open(files['config/default_network'], 'r') as f:
        default_network = yaml.safe_load(f.read())

    paths = list(filter(lambda x: _use_file(config, x), paths))
    for path in paths:
        content = path.read_text()

        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
        order = int(order)

        j = yaml.safe_load(content)
        if j:
            # TODO complain version - override version
            j['version'] = YAML_VERSION

            # set settings environment and the override settings after that
            for file in ['run/settings']:
                path = local_odoo_home / file
                if path.exists():
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

        odoodc = yaml.safe_load((local_odoo_home / 'machines/odoo/docker-compose.yml').read_text())

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

    temp_path = local_odoo_home / '.tmp.compose'
    if temp_path.is_dir():
        shutil.rmtree(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)
    try:
        temp_files = []
        for i, filecontent in enumerate(final_contents):
            path = temp_path / (str(i).zfill(10) + '.yml')
            with path.open('wb') as f:
                f.write(filecontent[1].encode('utf-8'))
            temp_files.append("-f")
            temp_files.append(path.name)

        cmdline = []
        cmdline.append("/usr/local/bin/docker-compose")
        cmdline += temp_files
        cmdline.append('config')

        d = deepcopy(os.environ)
        d.update(env)

        # have some tries; sometimes the compose files are not completley written
        # although turning off any buffers
        count = 0
        try:
            conf = __system(cmdline, cwd=temp_path, env=d, suppress_out=True)
        except Exception:
            if count > 5:
                raise
            print(cmdline)
            click.echo("Configuration files dont seem to be written completley retrying in 0.5 seconds to parse docker-compose configuration")
            raise
        # post-process config config
        conf = post_process_complete_yaml_config(yaml.safe_load(conf))
        conf = yaml.dump(conf, default_flow_style=False)

        with open(dest_file, 'w') as f:
            f.write(conf)
    finally:
        shutil.rmtree(temp_path)

def _setup_odoo_instances(config):
    def __add_location_files(config_path, dir):
        from pudb import set_trace
        set_trace()
        etc_proxy = Path("/etc/proxy")
        lines = []
        for file in dir.glob("**"):
            if file.is_file():
                lines.append("\tInclude " + str(etc_proxy / file.parent.name / file.name))
        __replace_in_file(config_path, "__INCLUDES__", '\n'.join(lines))

    if files['odoo_instances'].exists():
        for line in __file_get_lines(files['odoo_instances']):
            name, domain = line.strip().split(" ")
            print(name, domain, "please configure nodejs proxy to handle this")

def _export_settings(customs):
    from . import files
    from . import odoo_config
    from . import MyConfigParser

    if not files['settings'].exists():
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
    _files.append(dirs['odoo_home'] / 'machines/defaults')
    # optimize
    for filename in dirs['machines'].glob("**/default.settings"):
        _files.append(dirs['machines'] / filename)

    for dir in filter(lambda x: x.exists(), _get_settings_directories(customs)):
        if dir.is_file():
            _files.append(dir)
        elif dir.is_dir():
            for filename in os.listdir(dir):
                _files.append(dir / filename)
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

    c.write()

def _get_settings_directories(customs):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    from . import dirs
    customs_dir = odoo_config.customs_dir(customs)
    yield customs_dir / 'settings'
    yield Path('/etc_host/odoo/settings')
    yield Path('/etc_host/odoo/{}/settings'.format(customs))

def __postprocess_config(config):
    """
    keep if xxx in config queries for the toggle command. It sets
    a sub config file which does not contain all keys.
    """
    from . import odoo_config
    if "CUSTOMS" in config.keys():
        config['ODOO_VERSION'] = str(odoo_config.current_version())
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

    if "RUN_CALENDAR" in config.keys() and config.get("RUN_CALENDAR", "") == "1":
        config['RUN_CALENDAR_DB'] = "1"

@composer.command(name='toggle-settings')
@pass_config
@click.pass_context
def toggle_settings(ctx, config):
    if not __running_as_root_or_sudo():
        click.echo("Please run as root:")
        click.echo("sudo -E odoo toggle")
        sys.exit(1)
    from . import MyConfigParser
    myconfig = MyConfigParser(files['settings'])
    config_local = MyConfigParser(files['settings_etc_default_file'])

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

def _use_file(config, path):
    if 'etc' in path.parts or 'etc_host' in path.parts:
        return True
    if path.parent.parent.name == 'machines' and path.name == 'docker-compose.yml':
        if not getattr(config, "run_{}".format(path.parent.name)):
            return False
        if not any(x.startswith("run_") for x in path.parts):
            if getattr(config, 'run_{}'.format(path.parent.name)):
                return True

    if "run_odoo_version.{}.yml".format(config.odoo_version) in path.name:
        return True
    run = filter(lambda x: x.startswith("run_"), [y for x in path.parts for y in x.split(".")])
    for run in run:
        if getattr(config, run):
            return True
    run = filter(lambda x: x.startswith("!run_"), [y for x in path.parts for y in x.split(".")])
    for run in run:
        if not getattr(config, run):
            return True

    return False


Commands.register(do_reload, 'reload')
Commands.register(do_compose, 'compose')
