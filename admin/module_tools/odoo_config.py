# -*- coding: utf-8 -*-
import os
import time
import subprocess
from os.path import expanduser
from myconfigparser import MyConfigParser
from consts import VERSIONS
try:
    import psycopg2
except Exception:
    pass

def get_odoo_addons_paths():
    folders = subprocess.check_output(
        "find " + unicode(os.path.join(
            customs_dir(), "odoo"
        )) + "/ -name addons -type d| grep -v .git", shell=True)
    addons_paths = [
        x
        for x
        in folders.split("\n")
        if 'test' not in x and x.endswith("/addons") and 'odoo/odoo' not in x
    ]
    return addons_paths

def admin_dir():
    return os.path.join(odoo_root(), 'admin')

def customs_root():
    if os.getenv("DOCKER_MACHINE", "0") == "1":
        raise Exception("Not available within docker machine; there is only active_customs")
        # return os.path.dirname(os.environ['ACTIVE_CUSTOMS'])
    else:
        return os.path.join(odoo_root(), 'data', 'src', 'customs')

def customs_dir(customs=None):
    if os.getenv("DOCKER_MACHINE", "0") == "1":
        return os.environ['ACTIVE_CUSTOMS']

    c = customs or current_customs()
    return os.path.join(customs_root(), c)

def get_links_dir():
    return os.path.join(customs_dir(), 'links')

def module_dir(modulename):
    path = os.path.join(get_links_dir(), modulename)
    if not os.path.exists(path):
        for path in get_odoo_addons_paths():
            if os.path.exists(os.path.join(path, modulename)):
                path = os.path.join(path, modulename)
    return path

def get_version_from_customs(customs=None):
    with open(os.path.join(customs_dir(customs), '.version')) as f:
        return eval(f.read())

def install_file():
    return os.path.join(customs_dir(), 'install')

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
    if not os.path.isdir(odoo_home):
        odoo_home = '/opt/odoo'
    if not os.path.isdir(odoo_home):
        raise Exception("ODOO_HOME not found and not given per environment.")
    result = os.path.realpath(odoo_home)
    return result

def plaintextfile():
    path = os.path.join(customs_dir(), '.odoo.ast')
    return path

def _read_file(path, default=None):
    try:
        with open(path, 'r') as f:
            return (f.read() or '').strip()
    except Exception:
        return default

def get_env():
    # on docker machine self use environment variables; otherwise read from config file
    if os.getenv("DOCKER_MACHINE", "") == "1":
        return os.environ
    else:
        root = odoo_root()
        conf = MyConfigParser(os.path.join(root, 'run/settings'))
    return conf

def current_customs():
    result = os.getenv("CUSTOMS", get_env().get('CUSTOMS', ''))
    if not result:
        raise Exception("No Customs found. Please define customs=")
    return result

def current_version():

    version_file = os.path.join(customs_dir(), '.version')
    if not os.path.isfile(version_file):
        raise Exception("Missing: {}".format(version_file))
    with open(version_file, 'r') as f:
        return float(f.read())

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

def get_module_directory_in_machine(module_name):
    return os.path.join('/opt/odoo/addons_customs', module_name)

def translate_path_into_machine_path(path):
    path = os.path.realpath(path)
    path = os.path.join("/opt/odoo/active_customs", translate_path_relative_to_customs_root(path))
    return path

def translate_path_relative_to_customs_root(path):
    """
    The customs must contain a significant file named
    .customsroot to indicate the root of the customs
    """

    if 'data/src/modules' in path:
        path = path.split("data/src/modules")[1]
        # remove version
        path = '/'.join(path.split("/")[2:])
        # is in linked common dir
        path = os.path.join('common', path)
        print(path)
        return path

    path = os.path.realpath(path)
    parent = path

    while parent != '/':
        if os.path.exists(os.path.join(parent, '.customsroot')):
            break
        parent = os.path.dirname(parent)
    if parent == '/':
        raise Exception("no .customsroot found! - started at: {}".format(path))
    path = path[len(parent) + 1:]
    return path

def set_customs(customs, dbname=None):
    dbname = dbname or customs
    root = odoo_root()
    conf = MyConfigParser(os.path.join(root, 'run/settings'))
    conf['CUSTOMS'] = customs
    conf['DBNAME'] = dbname
    conf.write()
