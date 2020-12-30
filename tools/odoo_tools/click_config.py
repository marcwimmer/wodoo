import os
from pathlib import Path

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

    def __init__(self, quiet=False, project_name=None):
        from .consts import YAML_VERSION
        from . import odoo_config  # NOQA

        self.PROJECT_NAME = project_name
        self.YAML_VERSION = YAML_VERSION
        self.verbose = False
        self.force = False
        self.compose_version = YAML_VERSION
        self.setup_files_and_folders()
        self.quiet = quiet

    def setup_files_and_folders(self):
        from .init_functions import make_absolute_paths
        from .init_functions import _get_project_name
        from .init_functions import _get_default_anticipated_host_run_dir
        from .init_functions import get_use_docker
        from .init_functions import set_shell_table_title
        from .init_functions import _get_customs_root
        from . import odoo_config  # NOQA
        self.dirs = {}
        self.files = {}
        self.commands = {}

        self.WORKING_DIR = _get_customs_root(Path(os.getcwd()))
        self.CUSTOMS = self.WORKING_DIR and self.WORKING_DIR.name or None
        if not self.PROJECT_NAME:
            self.PROJECT_NAME = _get_project_name(self, self.WORKING_DIR)
        self.HOST_RUN_DIR = _get_default_anticipated_host_run_dir(self, self.WORKING_DIR, self.PROJECT_NAME)
        if not os.getenv("RUN_DIR"):
            # needed for get_env for example
            os.environ['RUN_DIR'] = str(self.HOST_RUN_DIR)
        self.NETWORK_NAME = "{}_default".format(self.PROJECT_NAME)
        make_absolute_paths(self, self.dirs, self.files, self.commands)
        self.use_docker = get_use_docker(self.files)
        self.dirs['customs'] = self.WORKING_DIR

        if self.dirs['customs']:
            self.files['commit'] = self.dirs['customs'] / self.files['commit'].name
        else:
            self.files['commit'] = None
        set_shell_table_title(self.PROJECT_NAME)

        from .program_settings import ProgramSettings
        self.runtime_settings = ProgramSettings(self.files['runtime_settings'])

    def forced(self):
        return Config.Forced(self)

    def _get_default_value(self, name_lower):
        if name_lower == 'owner_uid':
            return os.getuid()

    def __getattribute__(self, name):
        try:
            value = super(Config, self).__getattribute__(name)
            return value
        except AttributeError:
            from .myconfigparser import MyConfigParser  # NOQA
            if 'settings' not in self.files:
                return None
            myconfig = MyConfigParser(self.files['settings'])

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
                break
            else:
                value = self._get_default_value(name.lower())

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
        from .odoo_config import get_postgres_connection_params # NOQA
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
