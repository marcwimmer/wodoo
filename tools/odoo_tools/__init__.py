import sys
from datetime import datetime
import subprocess
from pathlib import Path
import imp
import inspect
import os
import glob
import click
from .tools import _file2env
from .lib_clickhelpers import AliasedGroup
import importlib

dir = Path(inspect.getfile(inspect.currentframe())).resolve().parent
sys.path.append(dir / '..' / 'module_tools')
from . import module_tools # NOQA
from .myconfigparser import MyConfigParser  # NOQA
from . import odoo_config  # NOQA
from .odoo_config import get_postgres_connection_params # NOQA
odoo_user_conf_dir = Path(os.environ["HOME"]) / '.odoo'

def _search_path(filename):
    filename = Path(filename)
    filename = filename.name
    for path in os.environ['PATH'].split(":"):
        path = Path(path)
        if (path / filename).exists():
            return str(path / filename)

def _get_customs_root(p):
    # arg_dir = p
    if p:
        while len(p.parts) > 1:
            if (p / 'MANIFEST').exists():
                return p
            p = p.parent
    # click.echo("Missing MANIFEST - file here in {}".format(arg_dir))

def _get_project_name(p):
    if not p:
        return

    settings = Path(os.environ['HOME']) / '.odoo' / 'settings'
    if settings.exists():
        if 'DEVMODE=1' in settings.read_text():
            return p.name

    if (p / '.git').exists():
        branch_name = subprocess.check_output([
            'git',
            'rev-parse',
            '--abbrev-ref',
            'HEAD'
        ], cwd=str(p)).decode('utf-8').strip()
    else:
        branch_name = ""
    if branch_name and branch_name not in [
        'master',
        'deploy',
        'stage',
    ]:
        branch_name = 'dev'
    return "_".join(x for x in [
        p.name,
        branch_name
    ] if x)


WORKING_DIR = _get_customs_root(Path(os.getcwd()))
PROJECT_NAME = _get_project_name(WORKING_DIR)
SCRIPT_DIRECTORY = Path(inspect.getfile(inspect.currentframe())).absolute().parent
CUSTOMS = WORKING_DIR and WORKING_DIR.name or None
HOST_RUN_DIR = None
if "HOST_HOME" in os.environ and PROJECT_NAME:
    HOST_RUN_DIR = Path(os.environ['HOST_HOME']) / '.odoo' / 'run' / PROJECT_NAME
NETWORK_NAME = "{}_default".format(PROJECT_NAME)
os.environ['CUSTOMS'] = CUSTOMS or ""
os.environ['PROJECT_NAME'] = PROJECT_NAME or ''
os.environ['CUSTOMS_DIR'] = WORKING_DIR and str(WORKING_DIR) or os.getenv("CUSTOMS_DIR", "")

class GlobalCommands(object):
    # so commands can call other commands
    def __init__(self):
        self.commands = {}

    def register(self, cmd, force_name=None):
        name = force_name or cmd.callback.__name__
        if name in self.commands:
            raise Exception()
        self.commands[name] = cmd

    def invoke(self, ctx, cmd, *args, **kwargs):
        return ctx.invoke(self.commands[cmd], *args, **kwargs)


Commands = GlobalCommands()

dirs = {
    'admin': 'admin',
    'odoo_home': '',
    'proxy_configs_dir': '${run}/proxy',
    'host_working_dir': '',
    'run': '${run}',
    'run/proxy': '${run}/proxy',
    'run/restore': '${run}/restore',
    'images': 'images',
    'images/proxy': 'images/proxy',
    'customs': '',
    'telegrambot': 'config/telegrambat',
}

files = {
    'docker_compose': '${run}/docker-compose.yml',
    'docker_compose_bin': _search_path('docker-compose'),
    'debugging_template_withports': 'config/template_withports.yml',
    'debugging_template_onlyloop': 'config/template_onlyloop.yml',
    'debugging_composer': '${run}/debugging.yml',
    'settings': '${run}/settings',
    'odoo_instances': '${run}/odoo_instances',
    'config/default_network': 'config/default_network',
    'run/odoo_debug.txt': '${run}/odoo_debug.txt',
    'run/snapshot_mappings.txt': '${run}/snapshot_mappings.txt',
    'images/proxy/instance.conf': 'images/proxy/instance.conf',
    'commit': 'odoo.commit',
    'settings_auto': "${run}/settings.auto",
    'user_settings': "~/.odoo/settings",
    'project_settings': "~/.odoo/settings.${project_name}",
}
commands = {
    'dc': [files['docker_compose_bin'], "-p", "$PROJECT_NAME", "-f",  "$docker_compose_file"],
}

def make_absolute_paths():
    dirs['odoo_home'] = Path(os.environ['ODOO_HOME'])

    def make_absolute(d):
        for k, v in list(d.items()):
            if not v:
                continue
            skip = False
            for value, name in [
                (HOST_RUN_DIR, '${run}'),
                (PROJECT_NAME, '${project_name}'),
            ]:
                if name in str(v):
                    if value:
                        v = str(v).replace(name, str(value))
                    else:
                        del d[k]
                        skip = True
                        break
            if skip:
                continue
            if str(v).startswith("~"):
                v = Path(os.path.expanduser(str(v)))

            if not str(v).startswith('/'):
                v = dirs['odoo_home'] / v
            d[k] = Path(v)

    make_absolute(dirs)
    make_absolute(files)

    # dirs['host_working_dir'] = os.getenv('LOCAL_WORKING_DIR', "")
    if 'docker_compose' in files:
        commands['dc'] = [x.replace("$docker_compose_file", str(files['docker_compose'])) for x in commands['dc']]


make_absolute_paths()

class Config(object):
    class Forced:
        def __init__(self, config):
            self.config = config
            self.force = config.force

        def __enter__(self):
            self.config.force = True
            return self.config

        def __exit__(self, type, value, traceback):
            self.config.force = self.force

    def __init__(self):
        self.verbose = False
        self.force = False
        self.compose_version = YAML_VERSION
        self.dirs = dirs
        self.files = files
        dirs['customs'] = odoo_config.customs_dir()

        if dirs['customs']:
            files['commit'] = dirs['customs'] / files['commit'].name
        else:
            files['commit'] = None

    def forced(self):
        return Config.Forced(self)

    def __getattribute__(self, name):

        try:
            value = super(Config, self).__getattribute__(name)
            return value
        except AttributeError:
            myconfig = MyConfigParser(files['settings'])

            convert = None
            if name.endswith('_as_int'):
                convert = 'asint'
                name = name[:-len('_as_int')]
            elif name.endswith('_as_bool'):
                convert = 'asbool'
                name = name[:-len('_as_bool')]

            for tries in [name, name.lower(), name.upper()]:
                value = ''
                if tries not in myconfig.keys():
                    continue
                value = myconfig.get(tries, "")
                if convert:
                    if convert == 'asint':
                        value = int(value or '0')

                if value == "1":
                    value = True
                elif value == "0":
                    value = False
            return value
        except Exception:
            raise

    def get_odoo_conn(self):
        from .tools import DBConnection
        host, port, user, password = get_postgres_connection_params()
        conn = DBConnection(
            self.dbname,
            host,
            port,
            user,
            password
        )
        return conn


pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group(cls=AliasedGroup)
@click.option("-f", "--force", is_flag=True)
@pass_config
def cli(config, force):
    config.force = force

from . import lib_clickhelpers  # NOQA
from . import lib_composer # NOQA
from . import lib_admin # NOQA
from . import lib_backup # NOQA
from . import lib_control # NOQA
from . import lib_db # NOQA
from . import lib_global # NOQA
from . import lib_lang # NOQA
from . import lib_migrate # NOQA
from . import lib_module # NOQA
from . import lib_patches # NOQA
from . import lib_setup # NOQA
from . import lib_src # NOQA

YAML_VERSION = '3.5'
BACKUPDIR = Path("/host/dumps")
SAFE_KILL = ['postgres', 'redis']

# import container specific commands
from .tools import abort # NOQA
from .tools import __dcrun # NOQA
from .tools import __dc # NOQA

for module in dirs['images'].glob("**/__commands.py"):
    if module.is_dir():
        continue
    spec = importlib.util.spec_from_file_location(
        "dynamic_loaded_module", str(module),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
