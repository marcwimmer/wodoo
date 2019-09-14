import platform
from pathlib import Path
import importlib.util
import random
from copy import deepcopy
import subprocess
import time
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
from .tools import __replace_all_envs_in_str
from .tools import __running_as_root_or_sudo
from .tools import _file2env
from .tools import __append_line
from .tools import __makedirs
from .tools import __try_to_set_owner
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def composer(config):
    pass


@composer.command(name='reload', help="Switches to project in current working directory.")
@click.argument("db", required=False)
@click.option("--demo", is_flag=True, help="Enabled demo data.")
@pass_config
@click.pass_context
def do_reload(ctx, config, db, demo):
    from . import MyConfigParser
    CUSTOMS = os.environ['CUSTOMS']
    SETTINGS_FILE = files['settings']
    if SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()

    myconfig = MyConfigParser(SETTINGS_FILE)
    if not SETTINGS_FILE.exists():
        myconfig['CUSTOMS'] = CUSTOMS
        myconfig.write()

    # assuming we are in the odoo directory
    _do_compose(
        config=config,
        customs=CUSTOMS,
        db=db,
        demo=demo
    )

def _do_compose(config, customs='', db='', demo=False):
    """
    builds docker compose, proxy settings, setups odoo instances
    """
    from . import MyConfigParser
    from . import HOST_RUN_DIR, NETWORK_NAME
    os.environ['HOST_RUN_DIR'] = str(HOST_RUN_DIR)
    os.environ['NETWORK_NAME'] = NETWORK_NAME

    setup_settings_file(customs, db, demo)
    _export_settings(customs)
    _prepare_filesystem()
    _execute_after_settings()
    _prepare_yml_files_from_template_files(config)

    click.echo("Built the docker-compose file.")


def _prepare_filesystem():
    from . import MyConfigParser
    fileconfig = MyConfigParser(files['settings'])
    for subdir in ['config', 'sqlscripts', 'debug', 'proxy']:
        path = dirs['run'] / subdir
        __makedirs(path)
        __try_to_set_owner(
            int(fileconfig['OWNER_UID']),
            path
        )

def setup_settings_file(customs, db, demo):
    """
    Cleans run/settings and sets minimal settings;
    Puts default values in settings.d to override any values
    """
    from . import MyConfigParser
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
    config_compose_minimum = MyConfigParser(files['settings_auto'])
    config_compose_minimum.clear()
    for k in ['CUSTOMS', 'DBNAME', 'ODOO_DEMO']:
        if k in vals:
            config_compose_minimum[k] = vals[k]

    if not config_compose_minimum.get("POSTGRES_PORT", ""):
        # try to use same port again
        port = random.randint(10001, 30000)
        if files['settings'].exists():
            port = MyConfigParser(files['settings']).get("POSTGRES_PORT", str(random.randint(10001, 30000)))
        config_compose_minimum['POSTGRES_PORT'] = str(port)

    config_compose_minimum.write()

def _execute_after_compose(yml):
    """
    execute local __oncompose.py scripts
    """
    from . import MyConfigParser
    config = MyConfigParser(files['settings'])
    for module in dirs['images'].glob("**/__after_compose.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module", str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.after_compose(config, yml, dict(
            dirs=dirs,
        ))
    return yml

def _execute_after_settings():
    """
    execute local __oncompose.py scripts
    """
    from . import MyConfigParser
    config = MyConfigParser(files['settings'])
    for module in dirs['images'].glob("**/__after_settings.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module", str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.after_settings(config)
        config.write()

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
        dirs['images'],
        odoo_config.customs_dir(),
    ]:
        [_files.append(x) for x in dir.glob("**/docker-compose*.yml")]

    project_name = os.environ["PROJECT_NAME"]
    for d in [
        Path('/etc_host/odoo'),
        Path('/etc_host/odoo') / config.customs,
        Path('/etc_host/odoo') / project_name,
    ]:
        if d.exists():
            [_files.append(x) for x in d.glob("docker-compose*.yml")] # not recursive

    _prepare_docker_compose_files(config, files['docker_compose'], _files)

def _prepare_docker_compose_files(config, dest_file, paths):
    from . import YAML_VERSION
    from . import MyConfigParser

    final_contents = []

    if not dest_file:
        raise Exception('require destination path')

    with dest_file.open('w') as f:
        f.write("#Composed {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("version: '{}'\n".format(config.compose_version))
    myconfig = MyConfigParser(files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # add static yaml content to each machine
    default_network = yaml.safe_load(files['config/default_network'].read_text())

    paths = list(filter(lambda x: _use_file(config, x), paths))
    for path in paths:
        click.echo(path)
        content = path.read_text()

        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
        order = int(order)

        j = yaml.safe_load(content)
        if j:
            j['version'] = YAML_VERSION

            # set settings environment and the override settings after that
            for file in ['run/settings']:
                path = Path(os.environ['ODOO_HOME']) / file
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
        """

        yml['version'] = YAML_VERSION

        # remove restart policies, if not restart allowed:
        if not config.restart_containers:
            for service in yml['services']:
                if 'restart' in yml['services'][service]:
                    yml['services'][service].pop('restart')

        return yml

    # call docker compose config to get the complete config
    final_contents.sort(key=lambda x: x[0])

    temp_path = dirs['run'] / '.tmp.compose'
    if temp_path.is_dir():
        __empty_dir(temp_path)
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
        cmdline.append(str(files['docker_compose_bin']))
        cmdline += temp_files
        cmdline.append('config')

        d = deepcopy(os.environ)
        d.update(env)

        conf = subprocess.check_output(cmdline, cwd=temp_path, env=d)
        conf = yaml.safe_load(conf)
        conf = post_process_complete_yaml_config(conf)
        conf = _execute_after_compose(conf)

        dest_file.write_text(yaml.dump(conf, default_flow_style=False))

    finally:
        # shutil.rmtree(temp_path)
        pass

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
    fileconfig.write()

def _collect_settings_files(customs):
    from . import dirs
    _files = []
    _files.append(dirs['odoo_home'] / 'images/defaults')
    # optimize
    for filename in dirs['images'].glob("**/default.settings"):
        _files.append(dirs['images'] / filename)
    _files.append(files['settings_auto'])
    _files.append(files['user_settings'])
    if files['project_settings'].exists():
        _files.append(files['project_settings'])

    for dir in filter(lambda x: x.exists(), _get_settings_directories(customs)):
        click.echo("Searching for settings in: {}".format(dir))
        if dir.is_dir() and 'settings' not in dir.name:
            continue
        if dir.is_file():
            _files.append(dir)
        elif dir.is_dir():
            for file in dir.glob("*"):
                if file.is_dir():
                    continue
                _files.append(file)
    click.echo("Found following extra settings files:")
    for file in _files:
        if 'images' not in file.parts:
            click.echo(file)
            click.echo(file.read_text())

    return _files

def _make_settings_file(outfile, setting_files):
    """
    Puts all settings into one settings file
    """
    from . import MyConfigParser
    c = MyConfigParser(outfile)
    for file in setting_files:
        if not file:
            continue
        c2 = MyConfigParser(file)
        c.apply(c2)

    # expand variables
    for key in list(c.keys()):
        value = c[key]
        if "~" in value:
            c[key] = os.path.expanduser(value)

    c.write()

def _get_settings_directories(customs):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    from . import dirs
    customs_dir = odoo_config.customs_dir()
    project_name = os.environ["PROJECT_NAME"]
    yield customs_dir / 'settings'
    yield Path('/etc_host/odoo/settings')
    yield Path('/etc_host/odoo/{}/settings'.format(customs))
    yield Path('/etc_host/odoo/{}/settings'.format(project_name))
    yield Path('/home/{}/.odoo'.format(os.environ['USER']))

def __postprocess_config(config):
    """
    keep if xxx in config queries for the toggle command. It sets
    a sub config file which does not contain all keys.
    """
    from . import odoo_config
    if "CUSTOMS" in config.keys():
        config['ODOO_VERSION'] = str(odoo_config.current_version())

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
    import inquirer
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
    if 'etc' in path.parts:
        return True
    if path.parent.parent.name == 'images' and path.name == 'docker-compose.yml':
        if not getattr(config, "run_{}".format(path.parent.name)):
            return False
        if not any(x.startswith("run_") for x in path.parts):
            if getattr(config, 'run_{}'.format(path.parent.name)):
                return True

    if any(x for x in path.parts if 'platform_' in x):
        pl = 'platform_{}'.format(platform.system().lower())
        if not any(pl in x for x in path.parts):
            return False
        run_key = 'RUN_{}'.format(path.parent.name).upper()
        return getattr(config, run_key)

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
