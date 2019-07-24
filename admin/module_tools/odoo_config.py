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

def get_odoo_addons_paths():
    from .module_tools import Module
    folders = []
    c = customs_dir()

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

    return list(reversed(folders))

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

def MANIFEST():
    return eval(CUSTOMS_MANIFEST_FILE().read_text())

def MANIFEST_update(d):
    d['install'] = list(sorted(d['install']))
    d['OCA'] = list(sorted(d['OCA']))
    for mod in d['modules']:
        mod['urls'] = list(sorted(filter(lambda x: x, mod['urls'])))
    s = json.dumps(d, indent=4)
    CUSTOMS_MANIFEST_FILE().write_text(s)

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

def translate_path_into_machine_path(path):
    path = customs_dir() / translate_path_relative_to_customs_root(path)
    return path

def translate_path_relative_to_customs_root(path):
    """
    The customs must contain a significant file named
    MANIFEST to indicate the root of the customs
    """
    path = path.resolve()

    cmf = CUSTOMS_MANIFEST_FILE()
    for parent in path.resolve().parents:
        if str(parent.resolve().absolute()) == cmf.parent:
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
