import os
import sys
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

    def __init__(self, quiet=False, project_name=None, force=False, verbose=False, version=None):
        from .consts import YAML_VERSION
        from . import odoo_config  # NOQA

        from .init_functions import _get_customs_root

        self.WORKING_DIR = _get_customs_root(Path(os.getcwd()))
        self._host_run_dir = None
        self.project_name = project_name
        self.YAML_VERSION = YAML_VERSION
        self.verbose = verbose
        self.force = force
        self.compose_version = YAML_VERSION
        self.quiet = quiet
        self.restrict = []

    @property
    def project_name(self):
        return self._project_name

    @project_name.setter
    def project_name(self, value):
        self._project_name = value
        if self._project_name:
            os.environ["PROJECT_NAME"] = value
            self.HOST_RUN_DIR = Path(os.environ["HOME"]) / ".odoo" / "run" / value
        else:
            os.environ["PROJECT_NAME"] = ""
        self.setup_files_and_folders()

    @property
    def HOST_RUN_DIR(self):
        return self._host_run_dir

    @HOST_RUN_DIR.setter
    def HOST_RUN_DIR(self, value):
        self._host_run_dir = value
        if value:
            os.environ["HOST_RUN_DIR"] = str(value)
        self.setup_files_and_folders()

    def setup_files_and_folders(self):
        from .init_functions import get_use_docker
        from . import odoo_config  # NOQA

        self.dirs = {}
        self.files = {}
        self.commands = {}

        self.use_docker = get_use_docker(self.files)
        from .init_functions import make_absolute_paths

        make_absolute_paths(self, self.dirs, self.files, self.commands)

    def forced(self):
        return Config.Forced(self)

    def __getattribute__(self, name):
        try:
            value = super(Config, self).__getattribute__(name)
            return value
        except AttributeError:
            from .myconfigparser import MyConfigParser  # NOQA

            if "settings" not in self.files:
                return None
            myconfig = MyConfigParser(self.files["settings"])

            convert = None
            if name.endswith("_as_int"):
                convert = "asint"
                name = name[: -len("_as_int")]
            elif name.endswith("_as_bool"):
                convert = "asbool"
                name = name[: -len("_as_bool")]

            for tries in [name, name.lower(), name.upper()]:
                value = ""
                if tries not in myconfig.keys():
                    continue

                value = myconfig.get(tries, "")
                break

            if convert:
                if convert == "asint":
                    value = int(value or "0")

            if value == "1":
                value = True
            elif value == "0":
                value = False
            return value
        except Exception:
            raise

    def get_odoo_conn(self, inside_container=None):
        from .odoo_config import get_postgres_connection_params  # NOQA
        from .tools import DBConnection

        host, port, user, password = get_postgres_connection_params(
            inside_container=inside_container
        )
        conn = DBConnection(self.dbname, host, port, user, password)
        return conn
