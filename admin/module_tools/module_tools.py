# -*- coding: utf-8 -*-
import os
import codecs
import shutil
from Queue import Queue
from unidecode import unidecode
from odoo_config import admin_dir
from odoo_config import get_env
from odoo_config import odoo_root
from odoo_config import run_dir
from odoo_config import get_version_from_customs
from odoo_config import execute_managesh
from odoo_config import get_conn
from odoo_config import current_customs
from odoo_config import current_version
from odoo_config import current_db
from odoo_config import translate_path_into_machine_path
import traceback
import odoo_parser
from odoo_parser import get_view
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


ODOO_DEBUG_FILE = 'odoo_debug.txt'

def apply_po_file(pofile_path):
    """
    pofile_path - pathin in the machine
    """
    from pudb import set_trace
    set_trace()
    LANG = os.path.basename(pofile_path).split(".po")[0]
    module = get_module_of_file(pofile_path)
    langs = get_all_langs()

    for lang in langs:
        if not lang.startswith(LANG):
            continue

        tempfile_within_container = os.path.join('/opt/odoo/server/addons/', module, 'i18n', os.path.basename(pofile_path))

        execute_managesh('import-i18n', lang, tempfile_within_container)

def delete_qweb(modules):
    conn, cr = get_conn()
    try:
        if modules != 'all':
            cr.execute("select name from ir_module_module where name = %s", (modules,))
        else:
            cr.execute("select name from ir_module_module; ")

        for module in cr.fetchall():
            if not is_module_installed(module):
                continue
            cr.execute("""
                select
                    id, res_id
                from
                    ir_model_data
                where
                    module=%s and model='ir.ui.view' and res_id in (select id from ir_ui_view where type='qweb');
            """, [module])
            for view in cr.fetchall():
                cr.execute("""
                   delete from ir_model_data where id = %s;
                   delete from ir_ui_view where id = %s;
                """, [view[0], view[1]])
        conn.commit()
    finally:
        cr.close()
        conn.close()

def export_lang(current_file):
    module = get_module_of_file(current_file)
    langs = get_all_langs()
    for lang in langs:
        execute_managesh('export-i18n', lang, module)

        # here is the new generated po file now
        new_file_path = os.path.join(run_dir(), 'i18n', 'export.po')

        dest_path = os.path.join(
            get_path_to_current_odoo_module(current_file),
            'i18n',
            '{}.po'.format(lang)
        )
        shutil.copy(new_file_path, dest_path)

def get_all_customs():
    home = os.path.join(odoo_root(), 'data/src/customs')

    customs = []
    for dir in os.listdir(home):
        if os.path.isdir(os.path.join(home, dir)):
            customs.append(dir)
    return customs

def get_all_langs():
    langs = []
    conn, cr = get_conn()
    try:
        cr.execute("select code from res_lang")
        langs = [x[0] for x in cr.fetchall()]

    finally:
        cr.close()
        conn.close()
    return langs

def get_customs_modules(customs_path, mode):
    """

    Called by manage.sh update

    Fills contents of install file into installed modules-module.
    Increases Version on need.


    param customs_path: e.g. /opt/odoo/active_customs

    """

    assert mode in ['to_update', 'to_install']

    path_modules = os.path.join(customs_path, 'install')
    if os.path.isfile(path_modules):
        with open(path_modules, 'r') as f:
            content = f.read().split('\n')
            modules = [x for x in content[1:] if not x.startswith("#") and x]

            if mode == 'to_install':
                modules = [x for x in modules if not is_module_installed(x)]
            print ','.join(modules)

def get_module_of_file(filepath, return_path=False):

    if os.path.isdir(filepath):
        p = filepath
    else:
        p = os.path.dirname(filepath)

    def is_possible_module_dir(x):
        basename = os.path.basename(x)
        try:
            float(basename)
            return True, os.path.abspath(os.path.join(x, '../'))
        except:
            pass

        for m in MANIFESTS:
            if os.path.isfile(os.path.join(os.path.realpath(p), m)):
                return True, x

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

    if not return_path:
        return os.path.basename(p)
    else:
        return os.path.basename(p), p

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
    filepath = filepath.replace(path_to_module, "")
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

def is_module_installed(module):
    conn, cr = get_conn()
    try:
        cr.execute("select name, state from ir_module_module where name = %s", (module,))
        state = cr.fetchone()
        if not state:
            return False
        return state[1] in ['installed', 'to_upgrade']
    finally:
        cr.close()
        conn.close()


def make_customs(customs, version):
    path_customs = os.path.join(odoo_root(), 'data/src/customs', customs)
    if os.path.isdir(path_customs):
        raise Exception("Directory {} already exists!".format(path_customs))

    os.mkdir(path_customs)

    FNULL = open(os.devnull, 'w')
    cmd = "cd '{}'; {}/module_tools/make_customs {}".format(path_customs, admin_dir(), version)
    subprocess.check_call([cmd], shell=True, stdout=FNULL, stderr=subprocess.STDOUT)
    db = customs
    switch_customs_and_db(customs=customs, db=db)

def make_module(parent_path, module_name):
    """
    Creates a new odoo module based on a provided template.

    """
    complete_path = os.path.join(parent_path, module_name)
    if os.path.isdir(complete_path):
        raise Exception("Path already exists: {}".format(complete_path))

    os.mkdir(complete_path)

    subprocess.check_output([
        "{}/module_tools/make_module".format(admin_dir()),
        current_customs(),
        str(current_version()),
    ], cwd=complete_path)

    # enter in install file
    count = 0
    p = os.path.dirname(os.path.realpath(complete_path))
    while count < 30:
        count += 1
        p = os.path.dirname(p)
        install_file = os.path.join(p, 'install')
        if os.path.isfile(install_file):
            with open(install_file, 'r') as f:
                content = f.read().split("\n")
                content += [module_name]
                content0 = content[0]
                content = [x for x in sorted(content[1:], key=lambda line: line.replace("#", "")) if x]
            with open(install_file, 'w') as f:
                f.write(content0 + "\n")
                f.write("\n".join(content))

def update_module(filepath):
    module = get_module_of_file(filepath)
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        f.write('update_module:{}'.format(module))

def restart(quick):
    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        if quick:
            f.write('quick_restart')
        else:
            f.write('restart')

def remove_webassets():
    print "Removing web assets for {}".format(current_customs())
    conn, cr = get_conn()
    try:
        cr.execute("delete from ir_attachment where name ilike '/web/%web%asset%'")
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
                if n.get("id") == "module_install_notification":
                    n.getparent().remove(n)
                    matched = True
            if matched:
                with open(root + "/" + filename, "w") as f:
                    tree.write(f)


def run_test_file(path):
    if path:
        path = translate_path_into_machine_path(path)

    with open(os.path.join(run_dir(), ODOO_DEBUG_FILE), 'w') as f:
        if not path:
            f.write('last_unit_test')
        else:
            f.write('unit_test:{}:{}'.format(path, get_module_of_file(path)))

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

def syncsource(path, do_async=False):
    if path.endswith('.po'):
        machine_path = translate_path_into_machine_path(path)
        apply_po_file(machine_path)
    execute_managesh('update-source', path, do_async=do_async)

def switch_customs_and_db(customs, db):
    if not db:
        db = customs.split("_")[-1]

    execute_managesh('kill')
    version = get_version_from_customs(customs)
    conf = get_env()
    conf['CUSTOMS'] = customs
    conf['DBNAME'] = db
    conf['VERSION'] = str(version)
    conf.write()
    execute_managesh('update-source')
    execute_managesh('up', '-d', do_async=True)

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

    mod["data"] = []
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
                mod["data"].append(f)
        elif f.endswith(".js"):
            mod["js"].append(f)
        elif f.endswith(".css"):
            mod["css"].append(f)

    # keep test empty: use concrete call to test-file instead of testing on every module update
    mod["test"] = []

    # sort
    mod["data"].sort()
    mod["js"].sort()
    mod["css"].sort()
    if 'depends' in mod:
        mod["depends"].sort()

    # now sort again by inspecting file content - if __openerp__.sequence NUMBER is found, then
    # set this index; reason: some times there are wizards that reference forms and vice versa
    # but cannot find action ids
    # 06.05.2014: put the ir.model.acces.csv always at the end, because it references others, but security/groups always in front
    sorted_by_index = [] # contains tuples (index, filename)
    for filename in mod['data']:
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
    mod['data'] = [x[1] for x in sorted_by_index]

    if mod["qweb"]:
        mod["web"] = True
    if "application" not in mod:
        mod["application"] = False

    file = open(file_path, "wb")
    pp = pprint.PrettyPrinter(indent=4, stream=file)
    pp.pprint(mod)
    file.close()


def update_view_in_db(filepath, lineno, xml):
    module = get_module_of_file(filepath)
    xml = xml.split("\n")

    line = lineno
    xmlid = ""
    while line >= 0:
        if "<record " in xml[line]:
            # with search:
            match = re.findall('id=[\"\']([^\"^\']*)[\"\']', xml[line])
            if match:
                xmlid = match[0]
                break
        line -= 1

    def get_arch():
        _xml = xml
        if xml and xml[0] and 'encoding' in xml[0]:
            _xml = _xml[1:]
        doc = etree.XML("\n".join(_xml))
        for node in doc.xpath("//record"):
            if xmlid in node.get("id", ""):
                arch = node.xpath("field[@name='arch']")
                if arch:
                    inherit = node.xpath("field[@name='inherit_id']")
                    if not inherit or not inherit[0].get("ref", False):
                        inherit = None
                    if not inherit:
                        return etree.tounicode(arch[0].xpath("*")[0])
                    else:
                        arch = arch[0].xpath("*")
                        if arch[0].tag == "data":
                            result = arch[0]
                        else:
                            data = etree.Element("data")
                            for el in arch:
                                data.append(el)
                            result = data

                        s = etree.tounicode(result)
                        return s

        return None

    if xmlid:
        arch = get_arch()
        if arch:
            conn, cr = get_conn()
            try:
                cr.execute("select column_name from information_schema.columns where table_name = 'ir_ui_view'")
                columns = [x[0] for x in cr.fetchall()]
                arch_column = 'arch_db' if 'arch_db' in columns else 'arch'
                arch_fs_column = 'arch_fs' if 'arch_fs' in columns else None
                cr.execute("select res_id from ir_model_data where model='ir.ui.view' and module=%s and name=%s",
                             [
                                 module,
                                 xmlid
                             ])
                res = cr.fetchone()
                if res:
                    res_id = res[0]
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
                        except:
                            conn.rollback()

                conn.commit()
            except:
                conn.rollback()
            finally:
                cr.close()
                conn.close()
