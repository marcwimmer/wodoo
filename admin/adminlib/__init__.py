import sys
from pathlib import Path
import imp
import importlib
import inspect
import os
import glob
import click
from .tools import _file2env
from .lib_clickhelpers import AliasedGroup

stdinput = None
if not sys.stdin.isatty() and "SSH_CONNECTION" not in os.environ:
    stdinput = '\n'.join([x for x in sys.stdin])

dir = Path(inspect.getfile(inspect.currentframe())).resolve().parent
sys.path.append(os.path.join(dir, '../module_tools'))
import module_tools # NOQA
from module_tools.myconfigparser import MyConfigParser  # NOQA
from module_tools import odoo_config  # NOQA

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
    'proxy_configs_dir': 'run/proxy',
    'settings.d': 'run/settings.d',
    'host_working_dir': '',
    'run': 'run',
    'run/proxy': 'run/proxy',
    'run/restore': 'run/restore',
    'machines': 'machines',
    'machines/proxy': 'machines/proxy',
    'customs': '',
    'telegrambot': 'config/telegrambat',
}

files = {
    'docker_compose': 'run/docker-compose.yml',
    'debugging_template_withports': 'config/debugging/template_withports.yml',
    'debugging_template_onlyloop': 'config/debugging/template_onlyloop.yml',
    'debugging_composer': 'run/debugging.yml',
    'settings': 'run/settings',
    'settings_local': 'run/settings.d/local',
    'odoo_instances': 'run/odoo_instances',
    'config/default_network': 'config/default_network',
    'run/odoo_debug.txt': 'run/odoo_debug.txt',
    'run/snapshot_mappings.txt': 'run/snapshot_mappings.txt',
    'machines/proxy/instance.conf': 'machines/proxy/instance.conf',
    'machines/postgres/turndb2dev.sql': 'machines/postgres/turndb2dev.sql',
    'commit': 'odoo.commit',
}
commands = {
    'dc': ["/usr/local/bin/docker-compose", "-p", "$PROJECT_NAME", "-f",  "$docker_compose_file"],
}

def make_absolute_paths():
    dirs['odoo_home'] = Path(inspect.getfile(inspect.currentframe())).resolve().parent.parent.parent

    def make_absolute(d):
        for k, v in d.items():
            if not v:
                continue
            if not str(v).startswith('/'):
                d[k] = dirs['odoo_home'] / v

    make_absolute(dirs)
    make_absolute(files)

    dirs['host_working_dir'] = os.getenv('LOCAL_WORKING_DIR', "")
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
        if self.customs:
            dirs['customs'] = odoo_config.customs_dir(customs=self.customs)
        else:
            dirs['customs'] = None

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
        conn = DBConnection(
            self.dbname,
            self.db_host,
            self.db_port,
            self.db_user,
            self.db_pwd
        )
        return conn


pass_config = click.make_pass_decorator(Config, ensure=True)

@click.group(cls=AliasedGroup)
@click.option("-f", "--force", is_flag=True)
@pass_config
def cli(config, force):
    config.force = force


__import__("adminlib.lib_clickhelpers")
__import__("adminlib.lib_composer")
__import__("adminlib.lib_admin")
__import__("adminlib.lib_backup")
__import__("adminlib.lib_control")
__import__("adminlib.lib_db")
__import__("adminlib.lib_global")
__import__("adminlib.lib_image")
__import__("adminlib.lib_lang")
__import__("adminlib.lib_migrate")
__import__("adminlib.lib_module")
__import__("adminlib.lib_patches")
# __import__("adminlib.lib_project")
__import__("adminlib.lib_setup")
__import__("adminlib.lib_src")
__import__("adminlib.lib_submodules")
# __import__("adminlib.lib_telegram")
# __import__("adminlib.lib_ticket")

SAFE_KILL = ['postgres', 'redis']
PLATFORM_OSX = "OSX"
PLATFORM_LINUX = "Linux"
YAML_VERSION = '3.5'
BACKUPDIR = "/host/dumps"
