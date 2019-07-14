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
    folders = []
    c = customs_dir()
    for f in (c / 'odoo').glob("**/addons"):
        if f.is_dir() and '.git' not in f.parts and 'test' not in f.relative_to(c).parts:
            folders.append(f.resolve().absolute())
    return folders

def admin_dir():
    return odoo_root() / 'admin'

def customs_root():
    return odoo_root() / 'data' / 'src' / 'customs'

def customs_dir(customs=None):
    c = customs or current_customs()
    return customs_root() / c

def get_links_dir():
    return customs_dir() / 'links'

def module_dir(modulename):
    path = get_links_dir() / modulename
    if not path.exists():
        for path in get_odoo_addons_paths():
            if (path / modulename).exists():
                path = path / modulename
    return path

def install_file():
    return customs_dir() / 'install'

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

def current_version():
    version_file = customs_dir() / '.version'
    if not version_file.exists():
        raise Exception("Missing: {}".format(version_file))
    return float(version_file.read_text().strip())

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

# def get_module_directory_in_machine(module_name):
    # return customs_dir() / 'links' / module_name

def translate_path_into_machine_path(path):
    path = customs_dir() / translate_path_relative_to_customs_root(path)
    return path

def translate_path_relative_to_customs_root(path):
    """
    The customs must contain a significant file named
    .customsroot to indicate the root of the customs
    """
    path = path.resolve()

    if 'data/src/modules' in str(path):
        raise Exception('todo')
        from pudb import set_trace
        set_trace()
        path = str(path).split("data/src/modules")[1]
        if path.startswith("/"):
            path = path[1:]
        path = Path(path)
        version = str(get_version_from_customs())
        if path.startswith(version + "/"):
            path = path[len(version + "/"):]
        # remove version needed for common/9.0/stock_modules/stock_free_available_items/views/product_form.xml
        # is in linked common dir
        path = os.path.join('common', path)
        return path

    for parent in path.resolve().parents:
        if (parent / '.customsroot').exists():
            path = str(path)[len(str(parent)) + 1:]
            return path
    else:
        raise Exception("no .customsroot found! - started at: {}".format(path))


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
