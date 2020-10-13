from contextlib import contextmanager
import platform
from pathlib import Path
import importlib.util
import random
from copy import deepcopy
import subprocess
import time
import importlib
import re
from datetime import datetime
import sys
import shutil
import hashlib
import os
import tempfile
import copy
import click
from . import tools
from .tools import __replace_all_envs_in_str
from .tools import __running_as_root_or_sudo
from .tools import _file2env
from .tools import __append_line
from .tools import _makedirs
from .tools import __try_to_set_owner
from .tools import __empty_dir
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .odoo_config import MANIFEST
from .tools import split_hub_url

@cli.group(cls=AliasedGroup)
@pass_config
def composer(config):
    pass


@composer.command(name='reload', help="Switches to project in current working directory.")
@click.option("--demo", is_flag=True, help="Enabled demo data.")
@click.option("-d", "--db", required=False)
@click.option("-p", "--proxy-port", required=False)
@click.option("-m", "--mailclient-gui-port", required=False, default=None)
@click.option("-l", "--local", is_flag=True, help="Puts all files and settings into .odoo directory of source code")
@click.option("-P", '--project-name', help="Set Project-Name")
@click.option("--headless", is_flag=True, help="Dont start a web-server")
@click.option("--devmode", is_flag=True)
@pass_config
@click.pass_context
def do_reload(ctx, config, db, demo, proxy_port, mailclient_gui_port, local, project_name, headless, devmode):
    from .myconfigparser import MyConfigParser

    if headless and proxy_port:
        click.secho("Proxy Port and headless together not compatible.", fg='red')
        sys.exit(-1)

    click.secho("Current Project Name: {}".format(project_name or config.PROJECT_NAME), bold=True, fg='green')
    SETTINGS_FILE = config.files.get('settings')
    if SETTINGS_FILE and SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()

    _set_host_run_dir(config, local)
    # Reload config
    from .click_config import Config
    config = Config(project_name=project_name)

    defaults = {
        'config': config,
        'customs': config.CUSTOMS,
        'db': db,
        'demo': demo,
        'LOCAL_SETTINGS': '1' if local else '0',
        'CUSTOMS_DIR': config.WORKING_DIR,
    }
    if devmode:
        defaults['DEVMODE'] = 1
    if headless:
        defaults.update({
            'RUN_PROXY': 0,
            'RUN_PROXY_PUBLISHED': 0,
            'RUN_SSLPROXY': 0,
            'RUN_ROUNDCUBE': 0,
            'RUN_MAIL': 0,
            'RUN_CUPS': 0,
        })
    if proxy_port:
        defaults['PROXY_PORT'] = proxy_port
    if mailclient_gui_port:
        defaults["ROUNDCUBE_PORT"] = mailclient_gui_port

    # assuming we are in the odoo directory
    _do_compose(**defaults)

def _set_host_run_dir(config, local):
    from .init_functions import make_absolute_paths
    local_config_dir = (config.WORKING_DIR / '.odoo')
    if local:
        local_config_dir.mkdir(exist_ok=True)
    else:
        # remove probably existing local run dir
        if local_config_dir.exists():
            if not click.confirm(click.style(f"If you continue the local existing run directory {local_config_dir} is erased.", fg='red')):
                sys.exit(-1)
            shutil.rmtree(local_config_dir)
            click.secho("Please reload again.", fg='green')
            sys.exit(-1)

def _set_defaults(config, defaults):
    defaults['HOST_RUN_DIR'] = config.HOST_RUN_DIR
    defaults['NETWORK_NAME'] = config.NETWORK_NAME
    defaults['PROJECT_NAME'] = config.PROJECT_NAME

def _do_compose(config, customs='', db='', demo=False, **forced_values):
    """
    builds docker compose, proxy settings, setups odoo instances
    """
    from .myconfigparser import MyConfigParser
    from .settings import _export_settings

    defaults = {}
    _set_defaults(config, defaults)
    setup_settings_file(config, customs, db, demo, **defaults)
    _export_settings(config, customs, forced_values)
    _prepare_filesystem(config)
    _execute_after_settings(config)

    myconfig = MyConfigParser(config.files['settings'])
    if myconfig.get("USE_DOCKER", "1") == "1":
        _prepare_yml_files_from_template_files(config)

    click.echo("Built the docker-compose file.")


def _prepare_filesystem(config):
    from .myconfigparser import MyConfigParser
    fileconfig = MyConfigParser(config.files['settings'])
    for subdir in ['config', 'sqlscripts', 'debug', 'proxy']:
        path = config.dirs['run'] / subdir
        _makedirs(path)
        __try_to_set_owner(
            int(fileconfig['OWNER_UID']),
            path
        )

def setup_settings_file(config, customs, db, demo, **forced_values):
    """
    Cleans run/settings and sets minimal settings;
    Puts default values in settings.d to override any values
    """
    from .myconfigparser import MyConfigParser
    settings = MyConfigParser(config.files['settings'])
    if customs:
        if settings.get('CUSTOMS', '') != customs:
            settings.clear()
            settings['CUSTOMS'] = customs
            settings.write()
    vals = {}
    if customs:
        vals['CUSTOMS'] = customs
    vals['DBNAME'] = db or customs
    if demo:
        vals['ODOO_DEMO'] = "1" if demo else "0"
    vals.update(forced_values)

    for k, v in vals.items():
        if settings.get(k, '') != v:
            settings[k] = v
            settings.write()
    config_compose_minimum = MyConfigParser(config.files['settings_auto'])
    config_compose_minimum.clear()
    for k in vals.keys():
        config_compose_minimum[k] = vals[k]

    config_compose_minimum.write()

def _execute_after_compose(config, yml):
    """
    execute local __oncompose.py scripts
    """
    from .myconfigparser import MyConfigParser
    from .module_tools import Modules
    settings = MyConfigParser(config.files['settings'])
    for module in config.dirs['images'].glob("*/__after_compose.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module", str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.after_compose(config, settings, yml, dict(
            Modules=Modules(),
            tools=tools,
        ))
    settings.write()
    return yml

def _execute_after_settings(config):
    """
    execute local __oncompose.py scripts
    """
    from .myconfigparser import MyConfigParser
    settings = MyConfigParser(config.files['settings'])
    for module in config.dirs['images'].glob("**/__after_settings.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module", str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.after_settings(settings)
        settings.write()


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
        config.dirs['images'],
        odoo_config.customs_dir(),
        Path("/etc/odoo/"),
    ]:
        if not dir.exists():
            continue
        [_files.append(x) for x in dir.glob("**/docker-compose*.yml")]

    for d in [
        config.files['project_docker_compose.local'],
        config.files['project_docker_compose.home'],
        config.files['project_docker_compose.home.project'],
    ]:
        if not d.exists():
            click.secho(f"Hint: you may use configuration file {d}", fg='magenta')
            continue
        if d.is_file():
            _files.append(d)
        else:
            [_files.append(x) for x in d.glob("docker-compose*.yml")] # not recursive

    _prepare_docker_compose_files(config, config.files['docker_compose'], _files)

def _prepare_docker_compose_files(config, dest_file, paths):
    from .myconfigparser import MyConfigParser
    from .tools import abort
    import yaml

    final_contents = []

    if not dest_file:
        raise Exception('require destination path')

    with dest_file.open('w') as f:
        f.write("#Composed {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("version: '{}'\n".format(config.compose_version))
    myconfig = MyConfigParser(config.files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # add static yaml content to each machine
    default_network = yaml.safe_load(config.files['config/default_network'].read_text())

    paths = list(filter(lambda x: _use_file(config, x), paths))
    click.secho(f"\nUsing docker-compose files:", fg='green', bold=True)
    for path in paths:
        click.secho(str(path), fg='green')
    # collect further networks
    for path in paths:
        content = path.read_text()
        j = yaml.safe_load(content)
        for networkname, network in j.get('networks', {}).items():
            default_network['networks'][networkname] = network

    for path in paths:
        content = path.read_text()

        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
        order = int(order)

        j = yaml.safe_load(content)
        if not j:
            click.secho("Error loading content: \n{}".format(content), fg='red')
            sys.exit(-1)
            continue

        # default values in yaml file
        j['version'] = config.YAML_VERSION

        # set settings environment and the override settings after that
        for service in j.get('services', []):
            service = j['services'][service]
            service.setdefault('env_file', [])
            if isinstance(service['env_file'], str):
                service['env_file'] = [service['env_file']]
            if [x for x in service['env_file'] if x == '$ODOO_HOME/run/settings']:
                # no old format valid
                raise Exception('stop')

            file = '$HOST_RUN_DIR/settings'
            if not [x for x in service['env_file'] if x == file]:
                service['env_file'].append(file)

            service.setdefault('environment', [])

        j['networks'] = copy.deepcopy(default_network['networks'])

        content = yaml.dump(j, default_flow_style=False)
        content = __replace_all_envs_in_str(content, env)

        final_contents.append((order, content))

    def post_process_complete_yaml_config(yml):
        """
        This is after calling docker-compose config, which returns the
        complete configuration.
        """

        yml['version'] = config.YAML_VERSION

        # remove restart policies, if not restart allowed:
        if not config.restart_containers:
            for service in yml['services']:
                if 'restart' in yml['services'][service]:
                    yml['services'][service].pop('restart')

        # set hub source for all images, that are built:
        for service_name, service in yml['services'].items():
            if not service.get('build', False):
                continue
            hub = split_hub_url(config)
            if hub:
                # click.secho(f"Adding reference to hub {hub}")
                service['image'] = "/".join([
                    hub['url'],
                    hub['prefix'],
                    config.customs,
                    service_name + ":latest"
                ])

        return yml

    # call docker compose config to get the complete config
    final_contents.sort(key=lambda x: x[0])

    temp_path = config.dirs['run'] / '.tmp.compose'
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
        cmdline.append(str(config.files['docker_compose_bin']))
        cmdline += temp_files
        cmdline.append('config')

        d = deepcopy(os.environ)
        d.update(env)

        conf = subprocess.check_output(cmdline, cwd=temp_path, env=d)
        conf = yaml.safe_load(conf)
        conf = post_process_complete_yaml_config(conf)
        conf = _execute_after_compose(config, conf)

        dest_file.write_text(yaml.dump(conf, default_flow_style=False))

    finally:
        # shutil.rmtree(temp_path)
        pass

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
    myconfig = MyConfigParser(config.files['settings'])
    config_local = MyConfigParser(config.files['settings_etc_default_file'])

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
    config_local.write()

    Commands.invoke(ctx, 'reload')

def _use_file(config, path):
    if str(path.absolute()).startswith(str(config.dirs['user_conf_dir'].absolute())):
        return True
    if 'etc' in path.parts:
        return True
    if 'NO-AUTO-COMPOSE' in path.read_text():
        return False
    if path.parent.parent.name == 'images':
        if not getattr(config, "run_{}".format(path.parent.name)):
            return False
        if not any(".run_" in x for x in path.parts):
            # allower postgres/docker-compose.yml
            return True

    if any(x for x in path.parts if 'platform_' in x):
        pl = 'platform_{}'.format(platform.system().lower())
        if not any(pl in x for x in path.parts):
            return False
        run_key = 'RUN_{}'.format(path.parent.name).upper()
        return getattr(config, run_key)

    if "run_odoo_version.{}.yml".format(config.odoo_version) in path.name:
        return True

    # requires general run:
    if getattr(config, 'run_{}'.format(path.parent.name)):
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
