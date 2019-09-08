from contextlib import contextmanager
from datetime import datetime
import arrow
from collections import OrderedDict
import threading
import click
import json
from pathlib import Path
import os
import time
import subprocess
from os.path import expanduser
from .myconfigparser import MyConfigParser
from .consts import VERSIONS
try:
    import psycopg2
except Exception:
    pass

def get_odoo_addons_paths(relative=False):
    m = MANIFEST()
    c = customs_dir()
    res = []
    for x in m['addons_paths']:
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
        for file in folder.glob("**/__manifest__.py"):
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
        for oca_folder in list(c.glob(oca)):
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
    return Path(os.environ['CUSTOMS_DIR'])

def run_dir():
    "returns ~/odoo/run"
    from . import HOST_RUN_DIR
    if HOST_RUN_DIR is None:
        raise Exception("No RUN_DIR specified. Is HOST_HOME set?")
    return HOST_RUN_DIR

def odoo_root():
    #
    # be compatible with VIM on host and executed in container.
    #
    odoo_home = os.getenv('ODOO_HOME', False)
    if not odoo_home or not os.path.isdir(odoo_home):
        odoo_home = '/opt/odoo'
    if not os.path.isdir(odoo_home):
        raise Exception("ODOO_HOME not found and not given per environment.")
    result = Path(odoo_home).resolve()
    return result

def plaintextfile():
    path = customs_dir() / '.odoo.ast'
    return path

def _read_file(path, default=None):
    try:
        with open(path, 'r') as f:
            return (f.read() or '').strip()
    except Exception:
        return default

def get_env():
    # on docker machine self use environment variables; otherwise read from config file
    # if no run_dir provided, then provide minimal file
    if "RUN_DIR" in os.environ:
        file = Path(os.environ['RUN_DIR']) / 'settings'
        conf = MyConfigParser(file)
    else:
        conf = MyConfigParser({
            "CUSTOMS": os.getenv("CUSTOMS"),
        })
    return conf

def current_customs():
    result = os.getenv("CUSTOMS", "")
    if not result:
        result = get_env().get('CUSTOMS', '')
    if not result:
        raise Exception("No Customs found. Please define customs=")
    return result

def CUSTOMS_MANIFEST_FILE():
    return customs_dir().resolve().absolute() / "MANIFEST"

class MANIFEST_CLASS(object):
    def __init__(self):
        self.path = CUSTOMS_MANIFEST_FILE()

        self._apply_defaults()

    def _apply_defaults(self):
        d = self._get_data()
        d.setdefault('modules', [])
        # patches ?

        def has_url(pattern, x):
            return x.endswith(pattern) or x.endswith(pattern + ".git")

        mods = list(filter(lambda x: any(has_url('/patches', y) for y in x['urls']), d['modules']))
        if not mods:
            mods = self['modules']
            mods.append({
                'path': 'common',
                'branch': d['version'],
                'urls': [
                    "ssh://git@git.clear-consulting.de:50004/odoo/modules/patches",
                ],
            })
            self['modules'] = mods
        else:
            self.patch_dir = customs_dir() / mods[0]['path'] / 'patches'

        if 'not_allowed_commit_branches' not in d:
            self['not_allowed_commit_branches'] = [
                'master',
                'stage',
                'deploy',
            ]

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
        d['OCA'] = list(sorted(d['OCA']))
        for mod in d['modules']:
            mod['urls'] = list(sorted(filter(lambda x: x, mod['urls'])))
            mod['branch'] = str(mod['branch'])
        s = json.dumps(d, indent=4)
        CUSTOMS_MANIFEST_FILE().write_text(s)

    def rewrite(self):
        self._update(self._get_data())

def MANIFEST():
    return MANIFEST_CLASS()

def current_version():
    return float(MANIFEST()['version'])

def current_db():
    return get_env().get('DBNAME', '')

def get_postgres_connection_params():
    config = get_env()
    host = config["DB_HOST"]
    port = int(config.get("DB_PORT", "5432"))
    if os.getenv('DOCKER_MACHINE', "") != "1":
        host = '127.0.0.1'
        port = config['POSTGRES_PORT']
    password = config['DB_PWD']
    user = config['DB_USER']
    return host, port, user, password

def get_conn(db=None, host=None):
    if db != "template1":
        # waiting until postgres is up
        get_conn(db='template1')

    host, port, user, password = get_postgres_connection_params()
    db = db or current_db()
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
    try:
        path = path.resolve()
    except Exception:
        pass

    cmf = CUSTOMS_MANIFEST_FILE().resolve().absolute()

    if not str(path).startswith("/"):
        path = cmf.parent / path
        return path

    for parent in path.resolve().parents:
        if parent.resolve().absolute() == cmf.parent:
            path = str(path)[len(str(parent)) + 1:]
            return path
    else:
        raise Exception("No Customs MANIFEST File found. started at: {}".format(path))


MANIFEST_FILE = "__manifest__.py"
try:
    version = current_version()
except Exception:
    pass
else:
    if current_version() <= 10.0:
        MANIFEST_FILE = "__openerp__.py"
    else:
        MANIFEST_FILE = "__manifest__.py"
