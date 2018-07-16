# -*- coding: utf-8 -*-
import os
import codecs
import shutil
import uuid
try:
    from psycopg2 import IntegrityError
except Exception:
    pass
from Queue import Queue
from unidecode import unidecode
from odoo_config import admin_dir
from odoo_config import get_env
from odoo_config import odoo_root
from odoo_config import run_dir
from odoo_config import get_version_from_customs
from odoo_config import get_conn
from odoo_config import current_customs
from odoo_config import current_version
from odoo_config import current_db
from odoo_config import customs_dir
from odoo_config import install_file
from odoo_config import translate_path_into_machine_path
from odoo_config import set_customs
from odoo_config import translate_path_relative_to_customs_root
from odoo_config import get_module_directory_in_machine
from myconfigparser import MyConfigParser
import traceback
import odoo_parser
from odoo_parser import get_view
from odoo_parser import is_module_of_version
from odoo_parser import manifest2dict
import fnmatch
import re
import pprint
from consts import MANIFESTS
from lxml import etree
import subprocess
import xmlrpclib
import inspect
import sys
import threading
import glob


ODOO_DEBUG_FILE = 'debug/odoo_debug.txt'
try:
    current_version()
except Exception:
    LANG = 'de'
else:
    if current_version() == 7.0:
        LANG = 'de'
    else:
        LANG = os.getenv("ODOO_LANG", 'de_DE')  # todo from environment
host = "http://localhost:8069"

username = "admin"
pwd = "1"


def exe(*params):
    def login(username, password):
        socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (host))
        return socket_obj.login(current_db(), username, password)
    uid = login(username, pwd)
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (host))
    return socket_obj.execute(current_db(), uid, pwd, *params)


def apply_po_file(pofile_path):
    """
    pofile_path - pathin in the machine
    """
    modname = get_module_of_file(pofile_path)
    LANG = os.path.basename(pofile_path).split(".po")[0]
    pofile_path = os.path.join(modname, pofile_path.split(modname + "/")[-1])

    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        f.write('import_i18n:{}:{}'.format(LANG, pofile_path))

def delete_qweb(modules):
    conn, cr = get_conn()
    try:
        if modules != 'all':
            cr.execute("select name from ir_module_module where name = %s", (modules,))
        else:
            cr.execute("select name from ir_module_module; ")

        def erase_view(view_id):
            cr.execute("select id from ir_ui_view where inherit_id = %s;", (view_id, ))
            for child_view_id in [x[0] for x in cr.fetchall()]:
                erase_view(child_view_id)
            cr.execute("""
            select
                id
            from
                ir_model_data
            where
                model='ir.ui.view' and res_id =%s
            """, (view_id,))
            data_ids = [x[0] for x in cr.fetchall()]

            for data_id in data_ids:
                cr.execute("delete from ir_model_data where id = %s", (data_id,))

            sp = 'sp' + uuid.uuid4().hex
            cr.execute("savepoint {}".format(sp))
            try:
                cr.execute("""
                   delete from ir_ui_view where id = %s;
                """, [view_id])
                cr.execute("release savepoint {}".format(sp))

            except IntegrityError:
                cr.execute("rollback to savepoint {}".format(sp))

        for module in cr.fetchall():
            if not is_module_installed(module):
                continue
            cr.execute("""
                select
                    res_id
                from
                    ir_model_data
                where
                    module=%s and model='ir.ui.view' and res_id in (select id from ir_ui_view where type='qweb');
            """, [module])
            for view_id in [x[0] for x in cr.fetchall()]:
                erase_view(view_id)

        conn.commit()
    finally:
        cr.close()
        conn.close()

def export_lang(current_file):
    module = get_module_of_file(current_file)
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        f.write('export_i18n:{}:{}'.format(LANG, module))

def get_all_customs():
    home = os.path.join(odoo_root(), 'data/src/customs')

    customs = []
    for dir in os.listdir(home):
        if os.path.isdir(os.path.join(home, dir)):
            customs.append(dir)
    return customs

def get_all_manifests():
    """
    Returns a list of full paths of all manifests
    """
    for root, dirs, files in os.walk(customs_dir()):
        for filename in files:
            if any(x == filename for x in MANIFESTS):
                if is_module_dir_in_version(root)['ok']:
                    yield os.path.join(root, filename)

def get_modules_from_install_file():
    with open(install_file(), 'r') as f:
        content = f.read().split('\n')
        modules_from_file = [x for x in content if not x.strip().startswith("#") and x]
        return modules_from_file

def get_customs_modules(customs_path=None, mode=None):
    """

    Called by odoo update

    - fetches to be installed modules from install-file
    - selects all installed, to_be_installed, to_upgrade modules from db and checks wether
      they are from "us" or OCA
      (often those modules are forgotten to be updated)

    :param customs_path: e.g. /opt/odoo/active_customs

    """
    customs_path = customs_path or customs_dir()
    assert mode in [None, 'to_update', 'to_install']

    path_modules = install_file()
    if os.path.isfile(path_modules):
        modules_from_file = get_modules_from_install_file()
        modules = sorted(list(set(get_all_installed_modules() + modules_from_file)))

        installed_modules = set(list(get_all_installed_modules()))
        all_non_odoo = list(get_all_non_odoo_modules())

        modules = [x for x in all_non_odoo if x in installed_modules]
        modules += modules_from_file
        modules = list(set(modules))

        if mode == 'to_install':
            modules = [x for x in modules if not is_module_installed(x)]

        return modules
    return []

def get_all_non_odoo_modules(return_relative_manifest_paths=False):
    """
    Returns module names of all modules, that are from customs or OCA.
    """
    for manifest in get_all_manifests():
        relpath = translate_path_relative_to_customs_root(manifest)
        if any(relpath.startswith(x) for x in ['common/', 'modules/', 'OCA/']):
            if not return_relative_manifest_paths:
                yield get_module_of_file(manifest)
            else:
                yield relpath

def get_all_module_dependency_tree(all_manifests=None):
    """
    per modulename all dependencies - no hierarchy
    """
    result = {}
    all_manifests = all_manifests or get_all_manifests()

    for man in all_manifests:
        module_name = get_module_of_file(man)
        result.setdefault(module_name, set())
        info = manifest2dict(man)
        for dep in info.get('depends', []):
            result[module_name].add(dep)
    return result

def get_module_dependency_tree(manifest_path, all_manifests=None):
    """
    Dict of dicts
    """
    if not all_manifests:
        all_manifests = list(get_all_manifests())
    result = {}

    info = manifest2dict(manifest_path)

    for dep in info.get("depends"):
        if dep == 'base':
            continue
        result.setdefault(dep, {})

        mans = [x for x in all_manifests if get_module_of_file(x) == dep]
        for manifest in mans:
            for module_name, deps in get_module_dependency_tree(manifest, all_manifests).items():
                result[dep][module_name] = deps
    return result

def get_module_flat_dependency_tree(manifest_path, all_manifests=None):
    deptree = get_module_dependency_tree(manifest_path, all_manifests=all_manifests)
    result = set()

    def x(d):
        for k, v in d.items():
            result.add(k)
            x(v)

    x(deptree)
    return sorted(list(result))


def get_module_of_file(filepath, return_path=False, return_manifest=False):

    if os.path.isdir(filepath):
        p = filepath
    else:
        p = os.path.dirname(filepath)

    def is_possible_module_dir(x):
        basename = os.path.basename(x)
        for m in MANIFESTS:
            if os.path.isfile(os.path.join(os.path.realpath(p), m)):
                return True, x
        try:
            float(basename)
            return True, os.path.abspath(os.path.join(x, '../'))
        except Exception:
            pass

        return False, x

    limit = 30
    i = 0
    while True:
        i += 1
        if i > limit:
            raise Exception("No module found for: %s" % filepath)
        found, p = is_possible_module_dir(p)
        if found:
            break
        p = os.path.dirname(os.path.realpath(p))

    module_name = os.path.basename(p)
    try:
        float(module_name)
    except Exception:
        pass
    else:
        module_name = os.path.basename(os.path.dirname(p))

    if return_manifest:
        manifest = None
        for m in MANIFESTS:
            if os.path.isfile(os.path.join(p, m)):
                manifest = m
        if not manifest:
            raise Exception('error')
        return module_name, p, os.path.join(p, manifest)

    if return_path:
        return module_name, p
    if not return_path:
        return module_name

def get_manifest_path_of_module_path(module_path):
    for m in MANIFESTS:
        path = os.path.join(module_path, m)
        if os.path.isfile(path):
            return path


def get_path_to_current_odoo_module(current_file):
    """
    Fetches the path of __openerp__.py belonging to the current file
    """
    def is_module_path(path):
        for f in MANIFESTS:
            test = os.path.join(path, f)
            if os.path.exists(test):
                return test
        return None

    current_path = os.path.dirname(current_file)
    counter = 0
    while counter < 100 and len(current_path) > 1 and not is_module_path(current_path):
        current_path = os.path.dirname(current_path)
        counter += 1
    if counter > 40:
        pass
    return is_module_path(current_path)

def get_relative_path_to_odoo_module(filepath):
    path_to_module = get_path_to_current_odoo_module(filepath)
    for m in MANIFESTS:
        path_to_module = path_to_module.replace("/{}".format(m), "")
    filepath = filepath[len(path_to_module):]
    if filepath.startswith("/"):
        filepath = filepath[1:]
    return filepath

def goto_inherited_view(filepath, line, current_buffer):
    line -= 1  # line ist einsbasiert
    sline = current_buffer[line]
    context = odoo_parser.try_to_get_context(sline, current_buffer[:line + 1], filepath)

    filepath = None
    goto, filepath = None, None

    if isinstance(context, dict):
        if context["context"] == "arch" and "inherit_id" in context and context["inherit_id"]:
            inherit_id = context["inherit_id"]
            filepath, goto = get_view(inherit_id)

    if not filepath:
        # could be a qweb template
        for i in range(line, -1, -1):
            sline = current_buffer[i]
            if "t-extend=" in sline:
                sline = sline.split("t-extend=")[1]
                sline = sline.replace("\"", "'")
                template_name = sline.split("'")[1]
                return search_qweb(template_name)

    return filepath, goto

def is_module_dir_in_version(module_dir):
    version = current_version()
    if version >= 11.0:
        ok = is_module_of_version(module_dir)
        return {
            'ok': ok,
            'paths': [module_dir]
        }
    else:
        result = {'ok': False, "paths": []}
        info_file = os.path.join(module_dir, '.ln')
        if os.path.exists(info_file):
            info = manifest2dict(info_file)
            if isinstance(info, (float, long, int)):
                min_ver = info
                max_ver = info
                info = {'minimum_version': min_ver, 'maximum_version': max_ver}
            else:
                min_ver = info.get("minimum_version", 1.0)
                max_ver = info.get("maximum_version", 1000.0)
            if min_ver > max_ver:
                raise Exception("Invalid version: {}".format(module_dir))
            if float(version) >= float(min_ver) and float(version) <= float(max_ver):
                result['ok'] = True

            for m in MANIFESTS:
                if os.path.exists(os.path.join(module_dir, m)):
                    result['paths'].append(module_dir)
            if info.get('paths') and result['ok']:
                # used for OCA paths for example
                for path in info['paths']:
                    path = os.path.abspath(os.path.join(module_dir, path))
                    result['paths'].append(path)
        elif "/OCA/" in module_dir:
            relpath = module_dir.split(u"/OCA/")[1].split("/")
            if len(relpath) == 2:
                return {
                    'ok': True,
                    'paths': [module_dir],
                }

    return result

def get_uninstalled_modules_that_are_auto_install_and_should_be_installed():
    sql = """
        select
            mprior.name, mprior.state
        from
            ir_module_module_dependency d
        inner join
            ir_module_module m
        on
            m.id = d.module_id
        inner join
            ir_module_module mprior
        on
            mprior.name = d.name
        where
            m.name = '{module}';
    """
    conn, cr = get_conn()
    result = []
    try:
        cr.execute("select id, name from ir_module_module where state in ('uninstalled') and auto_install;")
        for mod in [x[1] for x in cr.fetchall()]:
            cr.execute(sql.format(module=mod))
            if all(x[1] == 'installed' for x in cr.fetchall()):
                # means that all predecessing modules are installed but not the one;
                # so it shoule be installed
                result.append(mod)
    finally:
        cr.close()
        conn.close()
    return result

def get_uninstalled_modules_where_others_depend_on():
    sql = """
        select
            d.name
        from
            ir_module_module_dependency d
        inner join
            ir_module_module m
        on
            m.id = d.module_id
        inner join
            ir_module_module mprior
        on
            mprior.name = d.name
        where
            m.state in ('installed', 'to install', 'to upgrade')
        and
            mprior.state = 'uninstalled';
    """
    conn, cr = get_conn()
    try:
        cr.execute(sql)
        return [x[0] for x in cr.fetchall()]
    finally:
        cr.close()
        conn.close()

def dangling_modules():
    conn, cr = get_conn()
    try:
        cr.execute("select count(*) from ir_module_module where state in ('to install', 'to upgrade', 'to remove');")
        return cr.fetchone()[0]
    finally:
        cr.close()
        conn.close()

def get_all_installed_modules():
    conn, cr = get_conn()
    try:
        cr.execute("select name from ir_module_module where state not in ('uninstalled', 'uninstallable', 'to remove');")
        return [x[0] for x in cr.fetchall()]
    finally:
        cr.close()
        conn.close()

def get_module_state(module):
    conn, cr = get_conn()
    try:
        cr.execute("select name, state from ir_module_module where name = %s", (module,))
        state = cr.fetchone()
        if not state:
            return False
        return state[1]
    finally:
        cr.close()
        conn.close()

def is_module_listed(module):
    conn, cr = get_conn()
    try:
        cr.execute("select count(*) from ir_module_module where name = %s", (module,))
        return bool(cr.fetchone()[0])
    finally:
        cr.close()
        conn.close()

def is_module_installed(module):
    conn, cr = get_conn()
    try:
        cr.execute("select name, state from ir_module_module where name = %s", (module,))
        state = cr.fetchone()
        if not state:
            return False
        return state[1] in ['installed', 'to upgrade']
    finally:
        cr.close()
        conn.close()

def is_module_listed_in_install_file_or_in_dependency_tree(module, all_manifests=None, all_module_dependency_tree=None):
    """
    Checks wether a module is in the install file. If not,
    then via the dependency tree it is checked, if it is an ancestor
    of the installed modules
    """
    all_manifests = all_manifests or get_all_manifests()
    depends = all_module_dependency_tree or get_all_module_dependency_tree(all_manifests=all_manifests)
    mods = get_customs_modules()
    if module in mods:
        return True

    def get_parents(module):
        for parent, dependson in depends.items():
            if module in dependson:
                yield parent

    def check_module(module):
        for p in get_parents(module):
            if p in mods:
                return True
            if check_module(p):
                return True
        return False

    return check_module(module)

def make_customs(customs, version):
    complete_path = os.path.join(odoo_root(), 'data/src/customs', customs)
    if os.path.exists(complete_path):
        raise Exception("Customs already exists.")
    shutil.copytree(os.path.join(odoo_root(), 'admin/customs_template', str(version)), complete_path)

def link_modules():
    LN_DIR = os.path.join(customs_dir(), 'links')
    IGNORE_PATHS = ['odoo/addons', 'odoo/odoo/test']

    if not os.path.isdir(LN_DIR):
        os.mkdir(LN_DIR)

    data = {'counter': 0}
    version = current_version()
    print "Linking all modules into: \n{}".format(LN_DIR)
    all_valid_module_paths = []

    for link in os.listdir(LN_DIR):
        os.unlink(os.path.join(LN_DIR, link))

    os.system("chown $ODOO_USER:$ODOO_USER \"{}\"".format(LN_DIR))

    def search_dir_for_modules(base_dir):

        def link_module(complete_module_dir):
            if version >= 11.0:
                if not os.path.exists(os.path.join(complete_module_dir, '__manifest__.py')):
                    return
                abs_root = os.path.abspath(base_dir)
                dir = os.path.abspath(complete_module_dir)
                module_name = get_module_of_file(complete_module_dir)
                target = os.path.join(LN_DIR, module_name)
                if os.path.exists(target):
                    if os.path.realpath(target) != complete_module_dir:
                        # let override OCA modules
                        if "/OCA/" in os.path.realpath(target):
                            os.unlink(target)
                        elif "/OCA/" in complete_module_dir:
                            os.unlink(target)
                        else:
                            raise Exception("Module {} already linked to {}; could not link to {}".format(os.path.basename(target), os.path.realpath(target), complete_module_dir))
                rel_path = complete_module_dir.replace(customs_dir(), "../active_customs")
                os.symlink(rel_path, target)
                data['counter'] += 1

            else:
                # prüfen, obs nicht zu den verbotenen pfaden gehört:
                abs_root = os.path.abspath(base_dir)
                dir = os.path.abspath(complete_module_dir)
                while dir != abs_root:
                    dir = os.path.abspath(os.path.join(dir, ".."))

                try:
                    module_name = get_module_of_file(complete_module_dir)
                except Exception:
                    return

                if not os.path.exists(os.path.join(complete_module_dir, "__openerp__.py")):
                    return

                target = os.path.join(LN_DIR, module_name)

                if os.path.exists(target):
                    if os.path.realpath(target) != complete_module_dir:
                        # let override OCA modules
                        if "/OCA/" in os.path.realpath(target):
                            os.unlink(target)
                        elif "/OCA/" in complete_module_dir:
                            os.unlink(target)
                        else:
                            raise Exception("Module {} already linked to {}; could not link to {}".format(os.path.basename(target), os.path.realpath(target), complete_module_dir))

                # if there are versions under the module e.g. 6.1, 7.0 then take name from parent
                try:
                    float(os.path.basename(target))
                    target = os.path.dirname(target)
                    target += "/%s" % os.path.basename(os.path.dirname(complete_module_dir))
                except Exception:
                    pass

                while os.path.islink(target):
                    os.unlink(target)

                rel_path = complete_module_dir.replace(customs_dir(), "../active_customs")
                os.symlink(rel_path, target)
                data['counter'] += 1

        def visit(root, dir, files):
            if '/.git/' in dir:
                return
            if '__pycache__' in dir:
                return
            if any(x in dir for x in IGNORE_PATHS):
                return
            if not is_module_of_version(dir):
                return
            all_valid_module_paths.append(dir)

        os.path.walk(base_dir, visit, False)

        def sort_paths(x):
            if '/OCA/' in x:
                return "0000_" + x
            return "1000_" + x

        for path in sorted(all_valid_module_paths, key=sort_paths):
            link_module(path)

    search_dir_for_modules(customs_dir())

def make_module(parent_path, module_name):
    """
    Creates a new odoo module based on a provided template.

    """
    version = get_version_from_customs()
    complete_path = os.path.join(parent_path, module_name)
    if os.path.isdir(complete_path):
        raise Exception("Path already exists: {}".format(complete_path))

    shutil.copytree(os.path.join(odoo_root(), 'admin/module_template', str(version)), complete_path)
    for root, dirs, files in os.walk(complete_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for filepath in files:
            filepath = os.path.join(root, filepath)
            with open(filepath, 'r') as f:
                content = f.read()
            content = content.replace("__module_name__", module_name)
            with open(filepath, 'w') as f:
                f.write(content)

    # enter in install file
    if os.path.isfile(install_file()):
        with open(install_file(), 'r') as f:
            content = f.read().split("\n")
            content += [module_name]
            content = [x for x in sorted(content[1:], key=lambda line: line.replace("#", "")) if x]
        with open(install_file(), 'w') as f:
            f.write("\n".join(content))

    link_modules()

def restart(quick):
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        if quick:
            f.write('quick_restart')
        else:
            f.write('restart')

def remove_webassets(dbname=None):
    print "Removing web assets for {}".format(current_customs())
    conn, cr = get_conn(db=dbname)
    try:
        cr.execute("delete from ir_attachment where name ilike '/web/%web%asset%'")
        cr.execute("delete from ir_attachment where name ilike 'import_bootstrap.less'")
        cr.execute("delete from ir_attachment where name ilike '%.less'")
        conn.commit()
    finally:
        cr.close()
        conn.close()


def remove_module_install_notifications(path):
    """
    entfernt aus /opt/odoo/versions aus den xml dateien records:
        model:mail.message
        id: module_install_notification

    entfernt via psql aus der angegebenen datenbank (parameter!), alle
    vorhandenen mail.messages und ir_model_data.

    versions sollte danach eingecheckt werden!
    """

    for root, dirnames, filenames in os.walk(path):
        filenames = [x for x in filenames if x.endswith(".xml")]

        for filename in filenames:
            path = os.path.join(root, filename)
            if not os.path.getsize(path):
                continue
            try:
                with open(path) as f:
                    tree = etree.parse(f)
            except Exception, e:
                print "error at {filename}: {e}".format(filename=filename, e=e)

            matched = False
            for n in tree.findall("//record[@model='mail.message']"):
                if "module_install_notification" in n.get('id'):
                    n.getparent().remove(n)
                    matched = True
            if matched:
                with open(root + "/" + filename, "w") as f:
                    tree.write(f)


def run_test_file(path):
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        if not path:
            f.write('last_unit_test')
        else:
            machine_path = translate_path_into_machine_path(path)
            if os.getenv("DOCKER_MACHINE", "0") == "1":
                path = machine_path
            module = get_module_of_file(path)
            # transform customs/cpb/common/followup/9.0/followup/tests/test_followup.py
            # to customs/cpb/common/followup/9.0/followup/tests/__init__.pyc so that
            # unit test runner is tricked to run the file
            # test_file = os.path.join(os.path.dirname(machine_path), "__init__.py")
            f.write('unit_test:{}:{}'.format(machine_path, module))

def search_qweb(template_name, root_path=None):
    root_path = root_path or odoo_root()
    pattern = "*.xml"
    for path, dirs, files in os.walk(os.path.abspath(root_path), followlinks=True):
        for filename in fnmatch.filter(files, pattern):
            filename = os.path.join(path, filename)
            if "/static/" not in filename:
                continue
            if os.path.basename(filename).startswith("."):
                continue
            with open(filename, "r") as f:
                filecontent = f.read()
            for idx, line in enumerate(filecontent.split("\n")):
                for apo in ['"', "'"]:
                    if "t-name={0}{1}{0}".format(apo, template_name) in line and "t-extend" not in line:
                        return filename, idx + 1


def set_ownership_exclusive(host=None):
    conn, cr = get_conn(db='template1', host=host)
    try:
        cr.execute("SELECT datname from pg_database")
        all_dbs = [x[0] for x in cr.fetchall() if not x[0].startswith("template") and x[0] != 'postgres']
        dbs = [x for x in all_dbs if x != current_db()]
        for db in dbs:
            cr.execute("alter database {} owner to postgres".format(db))
        if current_db() in all_dbs:
            cr.execute("alter database {} owner to odoo".format(current_db()))
        conn.commit()
    finally:
        cr.close()
        conn.close()

def update_module(filepath, full=False):
    module = get_module_of_file(filepath)
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        f.write('update_module{}:{}'.format('_full' if full else '', module))

def update_module_file(current_file):
    if not current_file:
        return
    # updates __openerp__.py the update-section to point to all xml files in the module;
    # except if there is a directory test; those files are ignored;
    file_path = get_path_to_current_odoo_module(current_file)
    module_path = os.path.dirname(file_path)

    file = open(file_path, "rb")
    mod = eval(file.read())
    file.close()

    # first collect all xml files and ignore test and static
    all_files = [
        os.path.join(root, name)
        for root, dirs, files in os.walk(os.path.dirname(file_path))
        for name in files
    ]
    for i in range(len(all_files)):
        file = all_files[i]
        common_prefix = os.path.commonprefix([file, file_path])
        if common_prefix != "/":
            all_files[i] = all_files[i][len(common_prefix):]

    DATA_NAME = 'data'
    if get_version_from_customs() <= 7.0:
        DATA_NAME = 'update_xml'

    mod[DATA_NAME] = []
    mod["qweb"] = []
    mod["js"] = []
    mod["demo_xml"] = []
    mod["css"] = []

    for f in all_files:
        if 'test/' in f:
            continue
        if f.endswith(".xml") or f.endswith(".csv") or f.endswith('.yml'):
            if f.startswith("demo%s" % os.sep):
                mod["demo_xml"].append(f)
            elif f.startswith("static%s" % os.sep):
                mod["qweb"].append(f)
            else:
                mod[DATA_NAME].append(f)
        elif f.endswith(".js"):
            mod["js"].append(f)
        elif f.endswith(".css"):
            mod["css"].append(f)

    # keep test empty: use concrete call to test-file instead of testing on every module update
    mod["test"] = []

    # sort
    mod[DATA_NAME].sort()
    mod["js"].sort()
    mod["css"].sort()
    if 'depends' in mod:
        mod["depends"].sort()

    # now sort again by inspecting file content - if __openerp__.sequence NUMBER is found, then
    # set this index; reason: some times there are wizards that reference forms and vice versa
    # but cannot find action ids
    # 06.05.2014: put the ir.model.acces.csv always at the end, because it references others, but security/groups always in front
    sorted_by_index = [] # contains tuples (index, filename)
    for filename in mod[DATA_NAME]:
        filename_xml = filename
        filename = os.path.join(module_path, filename)
        sequence = 0
        with open(filename, 'r') as f:
            content = f.read()
            if '__openerp__.sequence' in content:
                sequence = int(re.search('__openerp__.sequence[^\d]*(\d*)', content).group(1))
            elif os.path.basename(filename) == 'groups.xml':
                sequence = -999999
            elif os.path.basename(filename) == 'ir.model.access.csv':
                sequence = 999999
        sorted_by_index.append((sequence, filename_xml))

    sorted_by_index = sorted(sorted_by_index, key=lambda x: x[0])
    mod[DATA_NAME] = [x[1] for x in sorted_by_index]

    if mod["qweb"]:
        mod["web"] = True
    if "application" not in mod:
        mod["application"] = False

    write_manifest(file_path, mod)

def write_manifest(manifest_path, data):
    with open(manifest_path, "wb") as file:
        pp = pprint.PrettyPrinter(indent=4, stream=file)
        pp.pprint(data)

def update_view_in_db_in_debug_file(filepath, lineno):
    filepath = translate_path_into_machine_path(filepath)
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        f.write('update_view_in_db:{}|{}'.format(filepath, lineno))

def update_view_in_db(filepath, lineno):
    module = get_module_of_file(filepath)
    with open(filepath, 'r') as f:
        xml = f.read().split("\n")

    line = lineno
    xmlid = ""
    while line >= 0 and not xmlid:
        if "<record " in xml[line] or "<template " in xml[line]:
            line2 = line
            while line2 < lineno:
                # with search:
                match = re.findall('id=[\"\']([^\"^\']*)[\"\']', xml[line2])
                if match:
                    xmlid = match[0]
                    break
                line2 += 1

        line -= 1

    if '.' not in xmlid:
        xmlid = module + '.' + xmlid

    def extract_html(parent_node):
        arch = parent_node.xpath("*")
        result = None
        if arch[0].tag == "data":
            result = arch[0]
        else:
            data = etree.Element("data")
            for el in arch:
                data.append(el)
            result = data
        if result is None:
            return ""
        result = etree.tounicode(result, pretty_print=True)
        return result

    def get_arch():
        _xml = xml
        if xml and xml[0] and 'encoding' in xml[0]:
            _xml = _xml[1:]
        doc = etree.XML("\n".join(_xml))
        for node in doc.xpath("//*[@id='{}' or @id='{}']".format(xmlid, xmlid.split('.')[-1])):
            if node.tag == 'record':
                arch = node.xpath("field[@name='arch']")
            elif node.tag == 'template':
                arch = [node]
            else:
                raise Exception("impl")

            if arch:
                html = extract_html(arch[0])
                if node.tag == 'template':
                    doc = etree.XML(html)
                    datanode = doc.xpath("/data")[0]
                    if node.get('inherit_id', False):
                        datanode.set('inherit_id', node.get('inherit_id'))
                        datanode.set('name', node.get('name', ''))
                    else:
                        datanode.set('t-name', xmlid)
                        datanode.tag = 't'
                    html = etree.tounicode(doc, pretty_print=True)

                # if not inherited from anything, then base tag must not be <data>
                doc = etree.XML(html)
                if not doc.xpath("/data/*[@position] | /*[@position]"):
                    if doc.xpath("/data"):
                        html = etree.tounicode(doc.xpath("/data/*", pretty_print=True)[0])

                print html
                return html

        return None

    if xmlid:
        arch = get_arch()
        if '.' in xmlid:
            module, xmlid = xmlid.split('.', 1)
        if arch:
            conn, cr = get_conn()
            try:
                cr.execute("select column_name from information_schema.columns where table_name = 'ir_ui_view'")
                columns = [x[0] for x in cr.fetchall()]
                arch_column = 'arch_db' if 'arch_db' in columns else 'arch'
                arch_fs_column = 'arch_fs' if 'arch_fs' in columns else None
                print "Searching view/template for {}.{}".format(module, xmlid)
                cr.execute("select res_id from ir_model_data where model='ir.ui.view' and module=%s and name=%s",
                             [
                                 module,
                                 xmlid
                             ])
                res = cr.fetchone()
                if not res:
                    print "No view found for {}.{}".format(module, xmlid)
                else:
                    print 'updating view of xmlid: %s.%s' % (module, xmlid)
                    res_id = res[0]
                    cr.execute("select type from ir_ui_view where id=%s", (res_id,))
                    # view_type = cr.fetchone()[0]
                    cr.execute("update ir_ui_view set {}=%s where id=%s".format(arch_column), [
                        arch,
                        res_id
                    ])
                    conn.commit()
                    if arch_fs_column:
                        try:
                            rel_path = module + "/" + get_relative_path_to_odoo_module(filepath)
                            cr.execute("update ir_ui_view set arch_fs=%s where id=%s", [
                                rel_path,
                                res_id
                            ])
                        except Exception:
                            conn.rollback()

                    conn.commit()

                    if res:
                        exe("ir.ui.view", "write", [res_id], {'arch_db': arch})
            except Exception:
                conn.rollback()
                raise
            finally:
                cr.close()
                conn.close()


def check_if_all_modules_from_instal_are_installed():
    for module in get_modules_from_install_file():
        if not is_module_installed(module):
            print "Module {} not installed!".format(module)
            sys.exit(32)


if __name__ == '__main__':
    mod = get_module_of_file("/home/marc/odoo/data/src/customs/cpb/common/tools/module_tools/__openerp__.py")
    for x in get_all_non_odoo_modules():
        print x
