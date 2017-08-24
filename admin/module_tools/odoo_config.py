# -*- coding: utf-8 -*-
import os
import time
import configobj
import subprocess
from os.path import expanduser
from myconfigparser import MyConfigParser
from consts import VERSIONS
import psycopg2

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

def active_customs():
    return "/opt/openerp/active_customs"

def admin_dir():
    return os.path.join(odoo_root(), 'admin')

def customs_dir():
    c = current_customs()
    return os.getenv("ACTIVE_CUSTOMS", os.path.join(odoo_root(), 'data', 'src', 'customs', c))

def run_dir():
    "returns ~/odoo/run"
    path = odoo_root()
    result = os.path.join(path, 'run')
    if not os.path.exists(result):
        os.mkdir(result)
    return result

def odoo_root():
    result = os.getenv('ODOO_HOME', False)
    if not result:
        raise Exception("ODOO_HOME is not defined (usually ~/odoo)")
    result = os.path.realpath(result)
    return result

def plaintextfile():
    path = os.path.join(customs_dir(), '.odoo.ast')
    return path

def _read_file(path, default=None):
    try:
        with open(path, 'r') as f:
            return (f.read() or '').strip()
    except:
        return default

def get_env():
    # on docker machine self use environment variables; otherwise read from config file
    if os.getenv("DOCKER_MACHINE", "") == "1":
        return os.environ
    else:
        root = odoo_root()
        conf = MyConfigParser(os.path.join(root, 'settings'))
    return conf

def current_customs():
    result = os.getenv("CUSTOMS", get_env().get('CUSTOMS', ''))
    if not result:
        raise Exception("No Customs found. Please define customs=")
    return result

def current_version():
    return float(get_env().get('ODOO_VERSION', ''))

def current_db():
    return get_env().get('DBNAME', '')

def get_path_customs_root(customs=None):
    if not customs:
        customs = current_customs()
    return os.path.join(odoo_root(), 'data/src/customs/{}'.format(customs))

def get_version_from_customs(customs):
    with open(os.path.join(get_path_customs_root(customs), '.version')) as f:
        return eval(f.read())

def execute_managesh(*args, **kwargs):
    args = ['./manage.sh'] + list(args)
    proc = subprocess.Popen(args, cwd=odoo_root(), bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if not kwargs.get('do_async', False):
        output = ''
        while True:
            line = proc.stdout.readline()
            line = line.decode()
            if line == '':
                break
            output += line

        while proc.returncode is None:
            proc.wait()
        if proc.returncode:
            raise Exception(output)

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
    path = os.path.realpath(path)
    path = os.path.join(active_customs(), translate_path_relative_to_customs_root(path))
    return path

def translate_path_relative_to_customs_root(path):
    path = os.path.realpath(path)
    if path and path.startswith(odoo_root()):
        path = path[len(odoo_root()):]
    path = [x for x in path.split("/") if x]

    if path[0] == 'data':
        if path[1] == 'src':
            path = path[2:]
    if path[0] == 'customs':
        path = path[1:]
    if path[0] == current_customs():
        path = path[1:]
    path = os.path.join(*path)
    return path
