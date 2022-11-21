import os
from collections import ChainMap
import sys
from pathlib import Path
import importlib


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

    def __init__(
        self, quiet=False, project_name=None, force=False, verbose=False, version=None
    ):
        from .consts import YAML_VERSION
        from . import odoo_config  # NOQA

        from .tools import _get_customs_root

        try:
            self._WORKING_DIR = _get_customs_root(Path(os.getcwd()))
        except:
            # Case example odoo -p ...  called somewhere
            self._WORKING_DIR = None
        self._host_run_dir = None
        self._project_name = None
        self.YAML_VERSION = YAML_VERSION
        self.verbose = verbose
        self.force = force
        self.compose_version = YAML_VERSION
        self.quiet = quiet
        self.restrict = {}
        self.dirs = {}
        self.files = {}
        self.commands = {}

        self.project_name = project_name

    def _collect_files(self, files):
        import click

        for test in files:
            test = Path(test)
            if not test.exists():
                click.secho(f"Not found: {test}", fg="red")
                sys.exit(-1)
            yield test.absolute()

    def set_restrict(self, key, files):
        files = list(self._collect_files(files))
        self.restrict[key] = files

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, value):
        self._verbose = value
        os.environ["WODOO_VERBOSE"] = "1" if value else "0"

    @property
    def WORKING_DIR(self):
        return self._WORKING_DIR

    @WORKING_DIR.setter
    def WORKING_DIR(self, value):
        self._WORKING_DIR = value
        os.environ["CUSTOMS_DIR"] = self._WORKING_DIR

    @property
    def project_name(self):
        return self._project_name

    @project_name.setter
    def project_name(self, value):
        self._project_name = value
        if self._project_name:
            self.HOST_RUN_DIR = (
                Path(os.environ["HOME"]) / ".odoo" / "run" / self._project_name
            )
        else:
            self.HOST_RUN_DIR = ""
        os.environ["PROJECT_NAME"] = self._project_name or ""
        os.environ["project_name"] = self._project_name or ""
        self._setup_files_and_folders()
        os.environ["docker_compose"] = str(self.files.get("docker_compose")) or ""
        self.load_dynamic_modules()
        if self.verbose:
            print(self.files["docker_compose"])

    @property
    def HOST_RUN_DIR(self):
        return self._host_run_dir

    @HOST_RUN_DIR.setter
    def HOST_RUN_DIR(self, value):
        self._host_run_dir = value
        os.environ["HOST_RUN_DIR"] = str(value)
        self._setup_files_and_folders()

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

    @property
    def use_docker(self):
        from .myconfigparser import MyConfigParser  # NOQA

        try:
            myconfig = MyConfigParser(self.files["settings"])
        except Exception:
            USE_DOCKER = True
        else:
            USE_DOCKER = myconfig.get("USE_DOCKER", "1") == "1"

        return USE_DOCKER

    def _setup_files_and_folders(self):
        from . import odoo_config  # NOQA

        from .consts import default_dirs, default_files, default_commands

        for (input, output) in [
            (default_dirs, self.dirs),
            (default_files, self.files),
            (default_commands, self.commands),
        ]:
            output.clear()
            for k, v in input.items():
                output[k] = v

        self.dirs["odoo_home"] = Path(os.environ["ODOO_HOME"])

        def replace_keys(value, key_values):
            for k, v in key_values.items():
                p = ["${" + k + "}", f"${k}"]
                for p in p:
                    if p in str(value):
                        value = value.replace(p, str(v))
            return value

        def make_absolute(d, key_values={}):
            for k, v in list(d.items()):
                if not v:
                    continue
                skip = False
                v = replace_keys(v, key_values)

                for value, name in [
                    (self.HOST_RUN_DIR, "${run}"),
                    (self.WORKING_DIR, "${working_dir}"),
                    (self.project_name, "${project_name}"),
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

                if not str(v).startswith("/"):
                    v = self.dirs["odoo_home"] / v
                d[k] = Path(v)

        make_absolute(self.dirs)
        make_absolute(self.files, self.dirs)

        for k in self.commands:
            self.commands[k] = [
                replace_keys(
                    x,
                    ChainMap(
                        {
                            "project_name": self.project_name,
                            "PROJECT_NAME": self.project_name,
                            "working_dir": self.WORKING_DIR,
                            "WORKING_DIR": self.WORKING_DIR,
                            "host_run_dir": self.HOST_RUN_DIR,
                            "HOST_RUN_DIR": self.HOST_RUN_DIR,
                        },
                        self.__dict__,
                        self.files,
                        self.dirs,
                    ),
                )
                for x in self.commands[k]
            ]

    def load_dynamic_modules(self):
        parent_dir = self.dirs["images"]
        for module in parent_dir.glob("*/__commands.py"):
            if module.is_dir():
                continue
            spec = importlib.util.spec_from_file_location(
                "dynamic_loaded_module",
                str(module),
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
