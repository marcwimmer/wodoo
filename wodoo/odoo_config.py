from contextlib import contextmanager
from datetime import datetime
try:
    import arrow
except Exception:
    arrow = None
from collections import OrderedDict
import threading
from . import click
import json
from pathlib import Path
import os
import time
import subprocess
from os.path import expanduser
from .consts import VERSIONS
try:
    import psycopg2
except Exception:
    pass

def get_odoo_addons_paths(relative=False, no_extra_addons_paths=False, additional_addons_paths=False):
    m = MANIFEST()
    c = customs_dir()
    res = []
    addons_paths = m['addons_paths']
    if additional_addons_paths:
        addons_paths += additional_addons_paths
    for x in addons_paths:
        if no_extra_addons_paths:
            if x not in ['odoo/addons', 'odoo/odoo/addons']:
                continue
        if relative:
            res.append(x)
        else:
            res.append(c / x)
    return res


def _identify_odoo_addons_paths(show_conflicts=True):
    from .module_tools import Module
    folders = []
    c = customs_dir()

    modules = []

    def _get_modules_in_folder(folder):
        # find extra modules without repo
        for file in folder.glob("**/{}".format(MANIFEST_FILE())):
            if '.git' in file.parts:
                continue
            file = file.resolve().absolute()
            if file.parent.parent in folders:
                continue
            if any(x in file.relative_to(c).parts for x in {'test', 'tests', '.git'}):
                continue
            try:
                module = Module(file)
            except Module.IsNot:
                continue
            if module.in_version:
                if module.path.parent not in folders:
                    folders.append(module.path.parent)
                    modules.append(module)
            del file

    manifest = MANIFEST()

    oca_addons = [
        "addons_oca",
        "OCA",
        "addons_OCA",
        "*OCA",
    ]
    for oca in oca_addons:
        if oca not in os.listdir(c):
            continue

        for oca_folder in list(c.glob(oca)): # case insensitive on windows / macos
            _get_modules_in_folder(oca_folder)
            del oca_folder
        del oca

    for module in manifest['modules']:
        for url in module['urls']:
            repo_name = url.split("/")[-1].replace(".git", "")
            path = c / Path(module['path']) / repo_name
            _get_modules_in_folder(path)
            del url
        del module

    folders = list(reversed(folders))
    for odoo_folder in filter(lambda x: x.exists(), map(Path, [
        c / 'odoo' / 'openerp' / 'addons',  # backwards compatibility
        c / 'odoo' / 'addons',
        c / 'odoo' / 'odoo' / 'addons',
    ])):
        if not odoo_folder.exists():
            continue
        _get_modules_in_folder(odoo_folder)
        del odoo_folder
    folders = list(reversed(folders))
    _get_modules_in_folder(c)

    if show_conflicts:
        _detect_duplicate_modules(folders, modules)

    return folders


def _detect_duplicate_modules(folders, modules):
    from .module_tools import Module
    check_modules = {}
    c = customs_dir()
    for folder in folders:
        folder_rel = folder.relative_to(c)
        modules_in_folder = [x for x in modules if str(x.path.relative_to(c)).startswith(str(folder_rel))]
        for module in modules_in_folder:
            check_modules.setdefault(module.name, [])
            if module.path not in [x.path for x in check_modules[module.name]]:
                check_modules[module.name].append(module)

    for v in filter(lambda x: len(x) > 1, check_modules.values()):
        click.echo(click.style("Overridden Module: {}".format(v[0].name), bold=True, fg='green'))
        for i, module in enumerate(v):
            styles = dict(bold=True) if not i else {}
            s = str(module.path.relative_to(c))
            click.echo(click.style(s, **styles))
    time.sleep(2)

def customs_dir():
    env_customs_dir = os.getenv("CUSTOMS_DIR")
    if not env_customs_dir:
        manifest_file = Path(os.getcwd()) / 'MANIFEST'
        if manifest_file.exists():
            return manifest_file.parent
        else:
            click.secho("no MANIFEST file found in current directory.")
    return Path(env_customs_dir)

def run_dir():
    "returns ~/odoo/run"
    from . import HOST_RUN_DIR
    if HOST_RUN_DIR is None:
        raise Exception("No RUN_DIR specified. Is HOST_HOME set?")
    return HOST_RUN_DIR

def plaintextfile():
    path = customs_dir() / '.odoo.ast'
    return path

def _read_file(path, default=None):
    try:
        with open(path, 'r') as f:
            return (f.read() or '').strip()
    except Exception:
        return default

def MANIFEST_FILE():
    return customs_dir().resolve().absolute() / "MANIFEST"

class MANIFEST_CLASS(object):
    def __init__(self):
        self.path = MANIFEST_FILE()

        self._apply_defaults()

    def _apply_defaults(self):
        d = self._get_data()
        d.setdefault('modules', [])
        # patches ?

        self.patch_dir = customs_dir() / 'patches'

        if 'version' not in d:
            self['version'] = float(d['version'])

    def _get_data(self):
        return OrderedDict(eval(self.path.read_text() or "{}"))

    def __getitem__(self, key):
        data = self._get_data()
        return data[key]

    def get(self, key, default):
        return self._get_data().get(key, default)

    def __setitem__(self, key, value):
        data = self._get_data()
        data[key] = value
        self._update(data)

    def _update(self, d):
        d['install'] = list(sorted(d['install']))
        s = json.dumps(d, indent=4)
        MANIFEST_FILE().write_text(s)

    def rewrite(self):
        self._update(self._get_data())

def MANIFEST():
    return MANIFEST_CLASS()

def current_version():
    return float(MANIFEST()['version'])

def get_postgres_connection_params():
    config = get_settings()
    host = config["DB_HOST"]
    port = int(config.get("DB_PORT", "5432"))
    # using the linked port: For what? disturbs using an external database
    if os.getenv('ODOO_FRAMEWORK_KEEP_SQL_CONNECTION', "") != "1":
        if config.get("USE_DOCKER", "1") != "0" and config.get("RUN_POSTGRES", "") == "1":
            host = '127.0.0.1'
            port = config['POSTGRES_PORT']
    password = config['DB_PWD']
    user = config['DB_USER']
    return host, port, user, password

def get_settings():
    """
    Can run outside of host and inside host. Returns all values from 
    composed settings file.
    """
    from .myconfigparser import MyConfigParser  # NOQA
    if os.getenv("DOCKER_MACHINE") == "1":
        settings_path = Path("/tmp/settings")
        content = ""
        for k, v in os.environ.items():
            content += f"{k}={v}\n"
        settings_path.write_text(content)
    else:
        settings_path = Path(os.environ['HOST_RUN_DIR']) / 'settings'
    myconfig = MyConfigParser(settings_path)
    return myconfig

def get_conn(db=None, host=None):
    config = get_settings()
    if db != "postgres":
        # waiting until postgres is up
        get_conn(db='postgres')

    host, port, user, password = get_postgres_connection_params()
    db = db or config['DBNAME']
    connstring = "dbname={}".format(db)

    for combi in [
        ('password', password),
        ('host', host),
        ('port', port),
        ('user', user),
    ]:
        if combi[1]:
            connstring += " {}='{}'".format(combi[0], combi[1])

    conn = psycopg2.connect(connstring)
    cr = conn.cursor()
    return conn, cr

@contextmanager
def get_conn_autoclose(*args, **kwargs):
    conn, cr = get_conn(*args, **kwargs)
    try:
        yield cr
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        cr.close()
        conn.close()

def translate_path_into_machine_path(path):
    path = customs_dir() / translate_path_relative_to_customs_root(path)
    return path

def translate_path_relative_to_customs_root(path):
    """
    The customs must contain a significant file named
    MANIFEST to indicate the root of the customs
    """

    cmf = MANIFEST_FILE().absolute()
    if not str(path).startswith("/"):
        path = cmf.parent / path
        return path

    try:
        path = path.resolve()
    except Exception:
        pass

    for parent in path.resolve().parents:
        if parent.resolve().absolute() == cmf.parent:
            path = str(path)[len(str(parent)) + 1:]
            return path
    else:
        raise Exception("No Customs MANIFEST File found. started at: {}, Manifest: {}".format(path, cmf))


def manifest_file_names():
    result = "__manifest__.py"
    try:
        current_version()
    except Exception:
        pass
    else:
        if current_version() <= 10.0:
            result = "__openerp__.py"
        else:
            result = "__manifest__.py"
    return result
