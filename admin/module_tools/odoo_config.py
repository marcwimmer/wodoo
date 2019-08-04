from contextlib import contextmanager
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

def get_odoo_addons_paths(show_conflicts=False):
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

    for f in reversed(list((c / 'odoo').glob("**/addons"))):
        if not f.is_dir():
            continue
        # should be at least one valid module
        _get_modules_in_folder(f.resolve().absolute())
        del f

    manifest = MANIFEST()
    _get_modules_in_folder(c / 'OCA')
    for module in manifest['modules']:
        for url in module['urls']:
            repo_name = url.split("/")[-1].replace(".git", "")
            path = c / Path(module['path']) / repo_name
            _get_modules_in_folder(path)

    _get_modules_in_folder(c)

    if show_conflicts:
        _detect_duplicate_modules(folders, modules)

    return list(reversed(folders))

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

def admin_dir():
    return odoo_root() / 'admin'

def customs_root():
    return odoo_root() / 'data' / 'src' / 'customs'

def customs_dir(customs=None):
    c = customs or current_customs()
    return customs_root() / c

def run_dir():
    "returns ~/odoo/run"
    path = odoo_root()
    result = os.path.join(path, 'run')
    if not os.path.exists(result):
        os.mkdir(result)
    return result

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
    root = odoo_root()
    conf = MyConfigParser(root / Path('run/settings'))
    return conf

def current_customs():
    result = os.getenv("CUSTOMS", get_env().get('CUSTOMS', ''))
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
            d['modules'].append({
                'path': 'common',
                'branch': d['version'],
                'urls': [
                    "ssh://git@git.clear-consulting.de:50004/odoo/modules/patches",
                ],
            })
        else:
            self.patch_dir = customs_dir() / mods[0]['path'] / 'patches'

        d['version'] = float(d['version'])
        self._update(d)

    def _get_data(self):
        return eval(self.path.read_text() or "{}")

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

def get_conn(db=None, host=None):
    if db != "template1":
        # waiting until postgres is up
        get_conn(db='template1')

    config = get_env()
    db = db or current_db()
    connstring = "dbname={}".format(db)
    host = host or config["DB_HOST"]
    port = config.get("DB_PORT", "5432")
    for combi in [
            ('password', config.get("DB_PWD", "")),
            ('host', host),
            ('port', port),
            ('user', config.get("DB_USER", "")),
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
    path = path.resolve()

    cmf = CUSTOMS_MANIFEST_FILE().resolve().absolute()
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
