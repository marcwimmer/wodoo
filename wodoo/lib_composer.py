import traceback
import threading
from tabulate import tabulate
import time
import collections
import grp
import base64
import pwd
from contextlib import contextmanager
import platform
from pathlib import Path
import importlib.util
import random
from copy import deepcopy
import subprocess
import importlib
import sys
import shutil
import os
import tempfile
import copy
import click
from . import tools
from .tools import __replace_all_envs_in_str
from .tools import __running_as_root_or_sudo
from .tools import _makedirs
from .tools import __try_to_set_owner
from .tools import __empty_dir
from .tools import __remove_tree
from .tools import abort
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .odoo_config import MANIFEST
from .tools import execute_script

@cli.group(cls=AliasedGroup)
@pass_config
def composer(config):
    pass

@composer.command()
@click.option("--full", is_flag=True, help="Otherwise environment is shortened.")
@click.argument('service-name', required=False)
@pass_config
@click.pass_context
def config(ctx, config, service_name, full=True):
    import yaml
    content = yaml.safe_load(config.files['docker_compose'].read_text())

    def minimize(d):
        if isinstance(d, dict):
            for k in list(d.keys()):
                if k in ['environment']:
                    d.pop(k)
                    continue
                minimize(d[k])

        if isinstance(d, list):
            for item in d:
                minimize(item)

    if not full:
        minimize(content)

    if service_name:
        content = {service_name: content['services'][service_name]}

    content = yaml.dump(content, default_flow_style=False)
    process = subprocess.Popen(
        ["/usr/bin/less"],
        stdin=subprocess.PIPE
    )
    process.stdin.write(content.encode('utf-8'))
    process.communicate()


def _get_arch():
    arch = subprocess.check_output(["uname", "-m"], encoding='UTF-8').strip()
    return {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }[arch]

@composer.command(name='reload', help="Switches to project in current working directory.")
@click.option("--demo", is_flag=True, help="Enabled demo data.")
@click.option("-d", "--db", required=False)
@click.option("-p", "--proxy-port", required=False)
@click.option("-m", "--mailclient-gui-port", required=False, default=None)
@click.option("--headless", is_flag=True, help="Dont start a web-server")
@click.option("--devmode", is_flag=True)
@click.option("-c", "--additional_config", help="Base64 encoded configuration like in settings")
@click.option("--images-url", help="default: https://github.com/marcwimmer/odoo")
@click.option("--no-update-images", is_flag=True)
@pass_config
@click.pass_context
def do_reload(
    ctx, config, db, demo, proxy_port, mailclient_gui_port, headless,
    devmode, additional_config, images_url, no_update_images):
    from .myconfigparser import MyConfigParser

    if headless and proxy_port:
        click.secho((
            "Proxy Port and headless together not compatible."
        ), fg='red')
        sys.exit(-1)

    if not no_update_images:
        _download_images(config, images_url)
    config.TARGETARCH = _get_arch()

    click.secho(
        f"Current Project Name: {config.project_name}", bold=True, fg='green')
    SETTINGS_FILE = config.files.get('settings')
    if SETTINGS_FILE and SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()

    additional_config_file = None
    try:
        if additional_config:
            additional_config_file = Path(tempfile.mktemp(suffix='.'))
            additional_config_text = base64.b64decode(additional_config)
            additional_config_file.write_bytes(additional_config_text)
            additional_config = MyConfigParser(additional_config_file)
            click.secho(f"Additional config provided in {additional_config_file}:")
            for line in additional_config_text.decode('utf-8').split("\n"):
                click.secho("\t" + line)

        internal_reload(config, db, demo, devmode, headless, proxy_port, mailclient_gui_port, additional_config)

    finally:
        if additional_config_file and additional_config_file.exists():
            additional_config_file.unlink()

def get_arch():
    return platform.uname().machine # aarch64

def internal_reload(config, db, demo, devmode, headless, local, proxy_port, mailclient_gui_port, additional_config=None):
    defaults = {
        'config': config,
        'db': db,
        'demo': demo,
        'LOCAL_SETTINGS': '1' if local else '0',
        'CUSTOMS_DIR': config.WORKING_DIR,
    }
    if devmode:
        defaults['DEVMODE'] = 1
    if headless:
        defaults.update({
            'RUN_PROXY': 1,
            'RUN_PROXY_PUBLISHED': 0,
            'RUN_SSLPROXY': 0,
            'RUN_ROUNDCUBE': 1,
            'RUN_MAIL': 1,
            'RUN_CUPS': 0,
        })
    if proxy_port:
        defaults['PROXY_PORT'] = proxy_port
    if mailclient_gui_port:
        defaults["ROUNDCUBE_PORT"] = mailclient_gui_port

    if additional_config:
        for key in additional_config.keys():
            defaults[key] = additional_config[key]

        click.secho("Additional config: {defaults}")

    # assuming we are in the odoo directory
    _do_compose(**defaults)

    _execute_after_reload(config)

def _execute_after_reload(config):
    execute_script(config, config.files['after_reload_script'], "You may provide a custom after reload script here:")

def _set_defaults(config, defaults):
    defaults['HOST_RUN_DIR'] = config.HOST_RUN_DIR
    defaults['NETWORK_NAME'] = config.project_name
    defaults['project_name'] = config.project_name

def _do_compose(config, db='', demo=False, **forced_values):
    """
    builds docker compose, proxy settings, setups odoo instances
    """
    from .myconfigparser import MyConfigParser
    from .settings import _export_settings

    if os.getenv("SUDO_UID"):
        whoami = f"{os.environ['SUDO_USER']} {os.environ['SUDO_UID']}"
    else:
        whoami = str(pwd.getpwuid(os.getuid())[0])

    rows = []
    headers = ["Name", "Value"]
    rows.append(('project-name', config.project_name))
    rows.append(('cwd', os.getcwd()))
    rows.append(('whoami', whoami))
    rows.append(('run-dir', config.dirs['run']))
    rows.append(('cmd', ' '.join(sys.argv)))
    if config.restrict:
        for file in config.restrict:
            rows.append(("restrict to", file))
            del file

    click.secho(tabulate(rows, headers, tablefmt="fancy_grid"), fg='yellow')

    defaults = {}
    _set_defaults(config, defaults)
    setup_settings_file(config, db, demo, **defaults)
    _export_settings(config, forced_values)
    _prepare_filesystem(config)
    _execute_after_settings(config)

    _prepare_yml_files_from_template_files(config)

    click.echo("Built the docker-compose file.")

def _download_images(config, images_url):
    from . import consts
    if not config.dirs['images'].exists():
        subprocess.check_call([
            "git",
            "clone",
            images_url or consts.DEFAULT_IMAGES_REPO,
            config.dirs['images']
        ])
    subprocess.check_call([
        "git", "config", "--global",
        "--add", "safe.directory", str(
            config.dirs['images'])], cwd=config.dirs['images'])
    if subprocess.check_output([
        "git", "remote"], encoding="utf8", cwd=config.dirs['images']).strip():

        trycount = 0
        for i in range(10):
            trycount += 1
            try:
                subprocess.check_call([
                    "git", "pull"], cwd=config.dirs['images'])
            except Exception as ex:
                if trycount < 5:
                    time.sleep(random.randint(5, 30))
                else:
                    abort(str(ex))
            else:
                break
    branch = subprocess.check_output([
        "git", "rev-parse", "--abbrev-ref",
        "HEAD"], cwd=config.dirs['images'], encoding='utf-8').strip()
    sha = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%H"], cwd=config.dirs['images'], encoding='utf-8').strip()
    click.secho("--------------------------------------------------")
    click.secho(f"Images Branch: {branch}", fg='yellow')
    click.secho(f"Images SHA: {sha}", fg='yellow')
    if subprocess.check_output(["git", "diff", "--stat"], cwd=config.dirs['images']).strip():
        click.secho(f"{config.dirs['images']} is dirty", fg='red')
    else:
        click.secho(f"Clean repository", fg='yellow')
    click.secho("--------------------------------------------------")
    if os.getenv("SUDO_UID"):
        subprocess.check_call(["chown", os.environ['SUDO_USER'], '-R', config.dirs['images']])
    time.sleep(1.0)


def _prepare_filesystem(config):
    from .myconfigparser import MyConfigParser
    fileconfig = MyConfigParser(config.files['settings'])
    if os.getenv("SUDO_USER") and config.dirs['user_conf_dir'].exists():
        __try_to_set_owner(
            int(fileconfig['OWNER_UID']),
            config.dirs['user_conf_dir'],
        )
    for subdir in ['config', 'sqlscripts', 'debug', 'proxy']:
        path = config.dirs['run'] / subdir
        _makedirs(path)
        __try_to_set_owner(
            int(fileconfig['OWNER_UID']),
            path,
        )

def get_db_name(db, project_name):
    db = db or project_name

    if db and db[0] in "0123456789":
        db = 'db' + db
    for c in '?:/*\\!@#$%^&*()-.':
        db = db.replace(c, "_")
    db = db.lower()
    return db

def setup_settings_file(config, db, demo, **forced_values):
    """
    Cleans run/settings and sets minimal settings;
    Puts default values in settings.d to override any values
    """
    from .myconfigparser import MyConfigParser
    settings = MyConfigParser(config.files['settings'])
    vals = {}
    vals['DBNAME'] = get_db_name(db, config.project_name)
    if demo:
        vals['ODOO_DEMO'] = "1" if demo else "0"
    vals.update(forced_values)

    for k, v in vals.items():
        if settings.get(k, '') != v:
            settings[k] = v
            settings.write()

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
        try:
            module.after_compose(config, settings, yml, dict(
                Modules=Modules(),
                tools=tools,
            ))

        except Exception as ex:
            msg = traceback.format_exc()
            click.secho(f"Failed: {module.__file__}", fg='red')
            click.secho(msg)
            sys.exit(-1)

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
        if dir.is_file():
            _files += [dir]
        else:
            [_files.append(x) for x in dir.glob("**/docker-compose*.yml")]

    if config.restrict and config.restrict.get('docker-compose'):
        _files += config.restrict['docker-compose']
    else:
        for d in [
            config.files['project_docker_compose.local'],
            config.files['project_docker_compose.home'],
            config.files['project_docker_compose.home.project'],
        ]:
            if not d.exists():
                if config.verbose:
                    click.secho(f"Hint: you may use configuration file {d}", fg='magenta')
                continue
            if d.is_file():
                _files.append(d)
            else:
                [_files.append(x) for x in d.glob("docker-compose*.yml")] # not recursive

    _files2 =[]
    for x in _files:
        if x in _files2:
            continue
        _files2.append(x)
    _files = _files2
    del _files2
    _prepare_docker_compose_files(config, config.files['docker_compose'], _files)

def __resolve_custom_merge(whole_content, value):
    for k in list(value.keys()):
        if k == '__custom_merge':
            insert = whole_content['services'][value[k]]
            dict_merge(value, insert)
            value.pop(k)
            continue

        if isinstance(value[k], dict):
            __resolve_custom_merge(whole_content, value[k])
        elif isinstance(value[k], list):
            for item in value[k]:
                if isinstance(item, dict):
                    __resolve_custom_merge(whole_content, item)
    return whole_content

def __get_sorted_contents(paths):
    import yaml
    contents = []
    for path in paths:
        # now probably not needed anymore
        content = path.read_text()

        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
        order = int(order)

        contents.append((order, yaml.safe_load(content), path))

    contents = list(map(lambda x: x[1], sorted(contents, key=lambda x: x[0])))
    return contents

def __set_environment_in_services(content):
    for service in content.get('services', []):
        service = content['services'][service]
        service.setdefault('env_file', [])
        if isinstance(service['env_file'], str):
            service['env_file'] = [service['env_file']]

        file = '$HOST_RUN_DIR/settings'
        if not [x for x in service['env_file'] if x == file]:
            if service.get('labels', {}).get('odoo_framework.apply_env', '1') not in [0, '0', 'false', 'False']:
                service['env_file'].append(file)

        service.setdefault('environment', [])

def post_process_complete_yaml_config(config, yml):
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

    # apply build architecture
    for service_name, service in yml['services'].items():
        if not service.get('build', False):
            continue
        service['build'].setdefault('args', {})
        service['build']['args']['TARGETARCH'] = config.TARGETARCH


    # set container name to service name (to avoid dns names with _1)
    for service in yml['services']:
        yml['services'][service]['container_name'] = f"{config.project_name}_{service}"
        # yml['services'][service]['hostname'] = service # otherwise odoo pgcli does not work

    # set label from configuration settings starting with DOCKER_LABEL=123
    for service in yml['services']:
        service = yml['services'][service]
        for key in service['environment']:
            if key.startswith("DOCKER_LABEL_"):
                label_name = key[len("DOCKER_LABEL_"):]
                label_value = service['environment'][key]
                service.setdefault('labels', {})
                service['labels'][label_name] = label_value

    if config.REGISTRY:
        from .lib_docker_registry import _rewrite_compose_with_tags
        _rewrite_compose_with_tags(config, yml)

    return yml

def __run_docker_compose_config(config, contents, env):
    import yaml
    temp_path = config.dirs['run'] / '.tmp.compose'
    if temp_path.is_dir():
        __empty_dir(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)

    files = []
    for i, content in enumerate(contents):
        file_path = (temp_path / f'docker-compose-{str(i).zfill(5)}.yml')
        file_path.write_text(yaml.dump(content, default_flow_style=False))
        files.append(file_path)
        del file_path

    try:
        cmdline = [
            str(config.files['docker_compose_bin']),
        ]
        for file_path in files:
            cmdline += [
                "-f",
                file_path,
            ]
        cmdline += ['config']
        d = deepcopy(os.environ)
        d.update(env)

        # set current user id and docker group for probable dinds
        d['DOCKER_GROUP_ID'] = str(grp.getgrnam('docker').gr_gid)

        conf = subprocess.check_output(cmdline, cwd=temp_path, env=d)
        conf = yaml.safe_load(conf)
        shutil.rmtree(temp_path)
        return conf

    except Exception:
        raise
    finally:
        pass


def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """

    def _make_dict_if_possible(d, k):
        if k not in d:
            return
        if isinstance(d[k], list) and all(isinstance(x, str) for x in d[k]):
            new_d = {}
            for list_item in d[k]:
                if '=' in list_item:
                    key, value = list_item.split("=")
                elif ':' in list_item:
                    key, value = list_item.split(":", 1)
                else:
                    key, value = list_item, None
                new_d[key] = value
            d[k] = new_d

    for k, v in merge_dct.items():
        # handle
        # environment:
        #   A: B
        #   - A=B

        _make_dict_if_possible(merge_dct, k)

        if k in dct and not dct[k] and isinstance(merge_dct[k], dict):
            dct[k] = {}

        if (k in dct and isinstance(dct[k], dict) and isinstance(
                merge_dct[k], collections.abc.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:

            # merging lists of tuples and lists
            if k in dct:
                _make_dict_if_possible(dct, k)

            if k not in dct:
                dct[k] = merge_dct[k]

def _prepare_docker_compose_files(config, dest_file, paths):
    from .myconfigparser import MyConfigParser
    from .tools import abort
    import yaml

    if not dest_file:
        raise Exception('require destination path')

    myconfig = MyConfigParser(config.files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    paths = list(filter(lambda x: _use_file(config, x), paths))
    click.secho(f"\nUsing docker-compose files:", fg='green', bold=True)
    for path in paths:
        click.secho(str(path), fg='green')
        del path

    # make one big compose file
    contents = __get_sorted_contents(paths)
    contents = list(_apply_variables(config, contents, env))
    _explode_referenced_machines(contents)
    _fix_contents(contents)

    # call docker compose config to get the complete config
    content = __run_docker_compose_config(config, contents, env)
    content = post_process_complete_yaml_config(config, content)
    content = _execute_after_compose(config, content)
    dest_file.write_text(yaml.dump(content, default_flow_style=False))

def _fix_contents(contents):
    for content in contents:
        services = content.get('services')
        for service in services:
            service = services[service]
            # turn {"env_file": {"FILE1": null} --> ["FILE1"]
            if 'env_file' in service:
                if isinstance(service['env_file'], dict):
                    service['env_file'] = list(service['env_file'].keys())


def _explode_referenced_machines(contents):
    """
    with:
    service:
        machine:
            labels:
                compose.merge: service-name

    a service is referenced; this service is copied in its own file to match later that reference by its service
    name in docker compose config
    """
    import yaml
    needs_explosion = {}

    for content in contents:
        for service in content.get('services'):
            labels = content['services'][service].get('labels')
            if labels:
                if labels.get('compose.merge'):
                    needs_explosion.setdefault(labels['compose.merge'], set())
                    needs_explosion[labels['compose.merge']].add(service)

    for content in contents:
        for explode, to_explode in needs_explosion.items():
            if explode in content.get('services', []):
                for to_explode in to_explode:
                    if to_explode in content['services']:
                        src = deepcopy(content['services'][explode])
                        dict_merge(src, content['services'][to_explode])
                    else:
                        src = content['services'][explode]
                    content['services'][to_explode] = src

def _apply_variables(config, contents, env):
    import yaml
    # add static yaml content to each machine
    default_network = yaml.safe_load(config.files['config/default_network'].read_text())

    # extract further networks
    for content in contents:
        if not content:
            continue

        if isinstance(content, str):
            from .tools import abort
            abort((
                f"Invalid content {content}"
            ))
        for networkname, network in content.get('networks', {}).items():
            default_network['networks'][networkname] = network

        content['version'] = config.YAML_VERSION

        # set settings environment and the override settings after that
        __set_environment_in_services(content)
        content['networks'] = copy.deepcopy(default_network['networks'])

        content = yaml.dump(content, default_flow_style=False)
        content = __replace_all_envs_in_str(content, env)
        content = yaml.safe_load(content)
        yield content

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
    from . import odoo_config

    def check():
        if 'etc' in path.parts:
            return True
        if 'NO-AUTO-COMPOSE' in path.read_text():
            return False
        if 'images' in path.parts:
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
        if getattr(config, 'run_{}'.format(path.parent.name)) or 'run_' in path.name:
            run = list(filter(lambda x: x.startswith("run_"), [y for x in path.parts for y in x.split(".")]))
            for run in run:
                if getattr(config, run):
                    return True
                if getattr(config, run.lower().replace('run_', '')):
                    # make run_devmode possible; in config is only devmode set
                    return True
            run = filter(lambda x: x.startswith("!run_"), [y for x in path.parts for y in x.split(".")])
            for run in run:
                if not getattr(config, run):
                    return True
                if getattr(config, run.lower().replace('run_', '')):
                    return True
            return False

        if path.absolute() == config.files['docker_compose'].absolute():
            return False
        if str(path.absolute()).startswith(str(config.files['docker_compose'].parent.absolute())):
            return False

        return True

    res = check()
    if not res:
        if config.verbose:
            click.secho(f"ignoring file: {path}", fg='yellow')
    return res


Commands.register(do_reload, 'reload')
