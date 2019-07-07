from pathlib import Path
from copy import deepcopy
import os
import codecs
import shutil
import uuid
try:
    from psycopg2 import IntegrityError
except Exception:
    pass
from .odoo_config import admin_dir
from .odoo_config import get_env
from .odoo_config import odoo_root
from .odoo_config import run_dir
from .odoo_config import get_version_from_customs
from .odoo_config import get_conn
from .odoo_config import current_customs
from .odoo_config import current_version
from .odoo_config import current_db
from .odoo_config import customs_dir
from .odoo_config import install_file
from .odoo_config import translate_path_into_machine_path
from .odoo_config import translate_path_relative_to_customs_root
from .odoo_config import MANIFEST_FILE
from .myconfigparser import MyConfigParser
import traceback
from .odoo_parser import get_view
import fnmatch
import re
import pprint
from lxml import etree
import subprocess
try:
    import xmlrpclib
except Exception:
    import xmlrpc
    from xmlrpc import client as xmlrpclib
import inspect
import sys
import threading
import glob

ODOO_DEBUG_FILE = Path('debug/odoo_debug.txt')
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
            if not DBModules.is_module_installed(module):
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

def get_all_langs():
    sql = "select distinct code from res_lang where active = true;"
    conn, cr = get_conn()
    try:
        cr.execute(sql)
        langs = [x[0] for x in cr.fetchall() if x[0]]
    finally:
        cr.close()
        conn.close()
    return langs

def get_all_customs():
    home = odoo_root() / 'data/src/customs'

    customs = []
    for dir in home.glob("*"):
        if dir.is_dir():
            customs.append(dir.name)
    return customs

def get_modules_from_install_file():
    content = install_file().read_text().split("\n")
    modules_from_file = [x for x in content if not x.strip().startswith("#") and x]
    return modules_from_file

class DBModules(object):
    def __init__(self):
        pass

    @classmethod
    def check_if_all_modules_from_install_are_installed(clazz):
        for module in get_modules_from_install_file():
            if not clazz.is_module_installed(module):
                print("Module {} not installed!".format(module))
                sys.exit(32)

    @classmethod
    def get_uninstalled_modules_that_are_auto_install_and_should_be_installed(clazz):
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

    @classmethod
    def get_uninstalled_modules_where_others_depend_on(clazz):
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

    @classmethod
    def dangling_modules(clazz):
        conn, cr = get_conn()
        try:
            cr.execute("select count(*) from ir_module_module where state in ('to install', 'to upgrade', 'to remove');")
            return cr.fetchone()[0]
        finally:
            cr.close()
            conn.close()

    @classmethod
    def get_all_installed_modules(clazz):
        conn, cr = get_conn()
        try:
            cr.execute("select name from ir_module_module where state not in ('uninstalled', 'uninstallable', 'to remove');")
            return [x[0] for x in cr.fetchall()]
        finally:
            cr.close()
            conn.close()

    @classmethod
    def get_module_state(clazz, module):
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

    @classmethod
    def is_module_listed(clazz, module):
        conn, cr = get_conn()
        try:
            cr.execute("select count(*) from ir_module_module where name = %s", (module,))
            return bool(cr.fetchone()[0])
        finally:
            cr.close()
            conn.close()

    @classmethod
    def uninstall_module(clazz, module, raise_error=False):
        """
        Gentley uninstalls, without restart
        """
        conn, cr = get_conn()
        try:
            cr.execute("select state from ir_module_module where name = %s", (module,))
            state = cr.fetchone()
            if not state:
                return
            state = state[0]
            if state not in ['uninstalled']:
                cr.execute("update ir_module_module set state = 'uninstalled' where name = %s", (module,))
            conn.commit()
        finally:
            cr.close()
            conn.close()

    @classmethod
    def is_module_installed(clazz, module):
        if not module:
            raise Exception("no module given")
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

def make_customs(customs, version):
    complete_path = odoo_root() / Path('data/src/customs') / Path(customs)
    if complete_path.exists():
        raise Exception("Customs already exists.")
    shutil.copytree(str(odoo_root() / Path('admin/customs_template') / Path(str(version))), complete_path)

def make_module(parent_path, module_name):
    """
    Creates a new odoo module based on a provided template.

    """
    version = get_version_from_customs()
    complete_path = Path(parent_path) / Path(module_name)
    del parent_path
    if complete_path.exists():
        raise Exception("Path already exists: {}".format(complete_path))

    shutil.copytree(str(odoo_root() / Path('admin/module_template') / Path(str(version))), complete_path)
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
    if install_file().exists():
        with install_file().open('r') as f:
            content = f.read().split("\n")
            content += [module_name]
            content = [x for x in sorted(content[0:], key=lambda line: line.replace("#", "")) if x]
        with install_file().open('w') as f:
            f.write("\n".join(content))

    link_modules()

def restart(quick):
    if quick:
        write_debug_instruction('quick_restart')
    else:
        write_debug_instruction('restart')


def remove_module_install_notifications(path):
    """
    entfernt aus /opt/odoo/versions aus den xml dateien records:
        model:mail.message
        id: module_install_notification

    entfernt via psql aus der angegebenen datenbank (parameter!), alle
    vorhandenen mail.messages und ir_model_data.

    versions sollte danach eingecheckt werden!
    """

    for file in Path(path).glob("**/*.xml"):
        if 'migration' in file.parts:
            continue
        if file.name.startswith('.'):
            continue

            if not file.stat().st_size:
                continue
            try:
                with path.open('rb') as f:
                    tree = etree.parse(f)
            except Exception as e:
                print("error at {filename}: {e}".format(filename=file, e=e))

            matched = False
            for n in tree.findall("//record[@model='mail.message']"):
                if "module_install_notification" in n.get('id'):
                    n.getparent().remove(n)
                    matched = True
            if matched:
                with file.open("wb") as f:
                    tree.write(f)


def run_test_file(path):
    if not path:
        instruction = 'last_unit_test'
    else:
        machine_path = translate_path_into_machine_path(path)
        if os.getenv("DOCKER_MACHINE", "0") == "1":
            path = machine_path
        module = Module(path)
        instruction = 'unit_test:{}:{}'.format(machine_path, module.name)
    write_debug_instruction(instruction)

def search_qweb(template_name, root_path=None):
    root_path = root_path or odoo_root()
    pattern = "*.xml"
    for path, dirs, files in os.walk(str(root_path.resolve().absolute()), followlinks=True):
        for filename in fnmatch.filter(files, pattern):
            if filename.name.startswith("."):
                continue
            filename = Path(path) / Path(filename)
            if "static" not in filename.parts:
                continue
            filecontent = filename.read_text()
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
    module = Module(filepath)
    write_debug_instruction('update_module{}:{}'.format('_full' if full else '', module.name))

def update_view_in_db_in_debug_file(filepath, lineno):
    filepath = translate_path_into_machine_path(filepath)
    write_debug_instruction('update_view_in_db:{}|{}'.format(filepath, lineno))

def update_view_in_db(filepath, lineno):
    module = Module(filepath)
    xml = filepath.read_text().split("\n")

    line = lineno
    xmlid = ""
    while line >= 0 and not xmlid:
        if "<record " in xml[line] or "<template " in xml[line]:
            line2 = line
            while line2 < lineno:
                # with search:
                match = re.findall(r'\ id=[\"\']([^\"^\']*)[\"\']', xml[line2])
                if match:
                    xmlid = match[0]
                    break
                line2 += 1

        line -= 1

    if '.' not in xmlid:
        xmlid = module.name + '.' + xmlid

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

                print(html)
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
                module = Module.get_by_name(module)
                print("Searching view/template for {}.{}".format(module.name, xmlid))
                cr.execute("select res_id from ir_model_data where model='ir.ui.view' and module=%s and name=%s",
                             [
                                 module.name,
                                 xmlid
                             ])
                res = cr.fetchone()
                if not res:
                    print("No view found for {}.{}".format(module.name, xmlid))
                else:
                    print('updating view of xmlid: %s.%s' % (module.name, xmlid))
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
                            rel_path = module.name + "/" + str(filepath.relative_to(module.path))
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


class Modules(object):

    def __init__(self):

        def get_all_manifests():
            """
            Returns a list of full paths of all manifests
            """
            for file in customs_dir().glob("**/" + MANIFEST_FILE):
                yield file.absolute()

        self.modules = {}
        for m in get_all_manifests():
            self.modules[m.parent.name] = Module(m)

    def get_customs_modules(self, mode=None):
        """
        Called by odoo update

        - fetches to be installed modules from install-file
        - selects all installed, to_be_installed, to_upgrade modules from db and checks wether
          they are from "us" or OCA
          (often those modules are forgotten to be updated)

        :param customs_path: e.g. /opt/odoo/active_customs
        """
        assert mode in [None, 'to_update', 'to_install']

        path_modules = install_file()
        if path_modules.is_file():
            modules_from_file = get_modules_from_install_file()
            modules = sorted(list(set(DBModules.get_all_installed_modules() + modules_from_file)))

            installed_modules = set(list(DBModules.get_all_installed_modules()))
            all_non_odoo = list(map(lambda x: x.name, self.get_all_non_odoo_modules()))

            modules = [x for x in all_non_odoo if x in installed_modules]
            modules += modules_from_file
            modules = list(set(modules))

            if mode == 'to_install':
                modules = [x for x in modules if not DBModules.is_module_installed(x)]

            return modules
        return []

    def get_all_non_odoo_modules(self):
        """
        Returns module names of all modules, that are from customs or OCA.
        """
        for m in self.modules.values():
            if any(x in m.manifest_path.parts for x in ['common', 'modules', 'OCA']):
                yield m

    @classmethod
    def get_module_dependency_tree(clazz, module):
        """
        Dict of dicts

        'stock_prod_lot_unique': {
            'stock': {
                'base':
            },
            'product': {},
        }
        """
        result = {}

        def append_deps(mod, data):
            data[mod.name] = {}
            for dep in mod.manifest_dict['depends']:
                if dep == 'base':
                    continue
                dep_mod = [x for x in clazz.modules if x.name == dep]
                if dep_mod:
                    data[mod.name][dep_mod] = {}
                    append_deps(dep_mod[0], data[mod.name][dep_mod])

        append_deps(module, result)
        return result

    @classmethod
    def get_module_flat_dependency_tree(clazz, module):
        deptree = clazz.get_module_dependency_tree(module)
        result = set()

        def x(d):
            for k, v in d.items():
                result.add(k)
                x(v)

        x(deptree)
        return sorted(list(result))

class Module(object):

    class IsNot(Exception): pass

    def __init__(self, path):
        from .odoo_config import customs_root
        self.version = float(current_version())
        self.customs_root = customs_root()
        p = path if path.is_dir() else path.parent

        for p in [p] + list(p.parents):
            if (p / MANIFEST_FILE).exists():
                self._manifest_path = p / MANIFEST_FILE
                break
        if not getattr(self, '_manifest_path', ''):
            raise Module.IsNot("no module found for {}".format(path))
        self.name = self._manifest_path.parent.name
        self.path = self._manifest_path.parent

    @property
    def manifest_path(self):
        return self._manifest_path

    @property
    def manifest_dict(self):
        try:
            return eval(self.manifest_path.read_text()) # TODO safe
        except Exception:
            print("error at file: %s" % self.manifest_path)
            raise

    def __make_path_relative(self, path):
        path = path.resolve().absolute()
        path = path.relative_to(self.path)
        if not path:
            raise Exception("not part of module")

    def apply_po_file(self, pofile_path):
        """
        pofile_path - pathin in the machine
        """
        pofile_path = self.__make_path_relative(pofile_path)
        LANG = pofile_path.name.split(".po")[0]
        write_debug_instruction('import_i18n:{}:{}'.format(LANG, pofile_path))

    def export_lang(self, current_file, LANG):
        write_debug_instruction('export_i18n:{}:{}'.format(LANG, self.name))

    @classmethod
    def get_by_name(clazz, name):
        from pudb import set_trace
        set_trace()
        from .odoo_config import customs_dir
        path = customs_dir() / 'links' / name
        path = path.resolve()

        if path.is_dir():
            return Module(path)
        raise Exception("Module not found or not linked: {}".format(name))

    @property
    def dependent_moduless(self):
        """
        per modulename all dependencies - no hierarchy
        """
        result = {}
        for dep in self.manifest_dict.get('depends', []):
            result.add(Module.get_by_name(dep))

        return result

    def get_lang_file(self, lang):
        lang_file = self.path / "i18n" / lang.with_suffix('.po')
        if lang_file.exists():
            return lang_file

    @property
    def in_version(self):
        if self.version >= 10.0:
            version = self.manifest_dict.get('version', "")
            # enterprise modules from odoo have versions: "", "1.0" and so on... ok
            if not version:
                return True
            if len(version.split(".")) <= 3:
                # allow 1.0 2.2 etc.
                return True
            check = str(self.version).split('.')[0] + '.'
            return version.startswith(check)
        else:
            info_file = self.path / '.ln'
            if info_file.exists():
                info = eval(info_file.read_text())
                if isinstance(info, (float, int)):
                    min_ver = info
                    max_ver = info
                    info = {'minimum_version': min_ver, 'maximum_version': max_ver}
                else:
                    min_ver = info.get("minimum_version", 1.0)
                    max_ver = info.get("maximum_version", 1000.0)
                if min_ver > max_ver:
                    raise Exception("Invalid version: {}".format(self.path))
                if self.version >= float(min_ver) and self.version <= float(max_ver):
                    return True

            elif "OCA" in self.path.parts:
                relpath = str(self.path).split(u"/OCA/")[1].split("/")
                return len(relpath) == 2
        return False

    def update_assets_file(self):
        """
        Put somewhere in the file: assets: <xmlid>, then
        asset is put there.
        """
        assets_template = """
    <odoo><data>
    <template id="{id}" inherit_id="{inherit_id}">
        <xpath expr="." position="inside">
        </xpath>
    </template>
    </data>
    </odoo>
    """
        DEFAULT_ASSETS = "web.assets_backend"

        def default_dict():
            return {
                'stylesheets': [],
                'js': [],
            }

        files_per_assets = {
            # 'web.assets_backend': default_dict(),
            # 'web.report_assets_common': default_dict(),
            # 'web.assets_frontend': default_dict(),
        }
        # try to keep assets id
        filepath = self.path / 'views/assets.xml'
        current_id = None
        if filepath.exists():
            with filepath.open('r') as f:
                xml = f.read()
                doc = etree.XML(xml)
                for t in doc.xpath("//template/@inherit_id"):
                    current_id = t

        all_files = self.get_all_files_of_module()
        if get_version_from_customs() < 11.0:
            module_path = Path(str(self.path).replace("/{}/".format(get_version_from_customs()), ""))
            if module_path.endswith("/{}".format(get_version_from_customs())):
                module_path = "/".join(module_path.split("/")[:-1])

        for file in all_files:
            if file.name.startswith('.'):
                continue

            local_file_path = file.relative_to(self.path)

            if current_id:
                parent = current_id
            elif local_file_path.parts[0] == 'static':
                parent = DEFAULT_ASSETS
            elif local_file_path.parts[0] == 'report':
                parent = 'web.report_assets_common'
            else:
                continue
            files_per_assets.setdefault(parent, default_dict())

            if file.endswith('.less') or file.endswith('.css'):
                files_per_assets[parent]['stylesheets'].append(local_file_path)
            elif file.endswith('.js'):
                files_per_assets[parent]['js'].append(local_file_path)

        doc = etree.XML(assets_template)
        for asset_inherit_id, files in files_per_assets.items():
            parent = deepcopy(doc.xpath("//template")[0])
            parent.set('inherit_id', asset_inherit_id)
            parent.set('id', asset_inherit_id.split('.')[-1])
            parent_xpath = parent.xpath("xpath")[0]
            for style in files['stylesheets']:
                etree.SubElement(parent_xpath, 'link', {
                    'rel': 'stylesheet',
                    'href': style,
                })
            for js in files['js']:
                etree.SubElement(parent_xpath, 'script', {
                    'type': 'text/javascript',
                    'src': js,
                })
            doc.xpath("/odoo/data")[0].append(parent)

        # remove empty assets and the first template template
        for to_remove in doc.xpath("//template[1] | //template[xpath[not(*)]]"):
            to_remove.getparent().remove(to_remove)

        if not doc.xpath("//link| //script"):
            if filepath.exists():
                filepath.unlink()
        else:
            filepath.parent.mkdir(exist_ok=True)
            with filepath.open('w') as f:
                f.write(etree.tostring(doc, pretty_print=True))

    def get_all_files_of_module(self):
        for file in self.path.glob("**/*"):
            if file.name.startswith("."):
                continue
            if ".git" in file.parts:
                continue
            # relative to module path
            yield file

    def update_module_file(self):
        # updates __openerp__.py the update-section to point to all xml files in the module;
        # except if there is a directory test; those files are ignored;
        self.update_assets_file()
        mod = self.manifest_dict

        all_files = self.get_all_files_of_module()
        # first collect all xml files and ignore test and static
        DATA_NAME = 'data'
        if get_version_from_customs() <= 7.0:
            DATA_NAME = 'update_xml'

        mod[DATA_NAME] = []
        mod["qweb"] = []
        mod["js"] = []
        mod["demo_xml"] = []
        mod["css"] = []

        for f in all_files:
            local_path = str(f.relative_to(self.path))
            if 'test' in f.parts:
                continue
            if f.suffix in ['.xml', '.csv', '.yml']:
                if f.name.startswith("demo%s" % os.sep):
                    mod["demo_xml"].append(local_path)
                elif f.name.startswith("static%s" % os.sep):
                    mod["qweb"].append(local_path)
                else:
                    mod[DATA_NAME].append(local_path)
            elif f.suffix == '.js':
                mod["js"].append(local_path)
            elif f.suffix in ['.css', '.less']:
                mod["css"].append(local_path)

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
            filename = self.path / filename
            sequence = 0
            with filename.open('r') as f:
                content = f.read()
                if '__openerp__.sequence' in content:
                    sequence = int(re.search(r'__openerp__.sequence[^\d]*(\d*)', content).group(1))
                elif filename.name == 'groups.xml':
                    sequence = -999999
                elif filename.name == 'ir.model.access.csv':
                    sequence = 999999
            sorted_by_index.append((sequence, filename_xml))

        sorted_by_index = sorted(sorted_by_index, key=lambda x: x[0])
        mod[DATA_NAME] = [x[1] for x in sorted_by_index]

        if mod["qweb"]:
            mod["web"] = True
        if "application" not in mod:
            mod["application"] = False

        self.write_manifest(mod)

    def write_manifest(self, data):
        with self.manifest_path.open('w') as file:
            pp = pprint.PrettyPrinter(indent=4, stream=file)
            pp.pprint(data)


def link_modules():
    LN_DIR = Path(customs_dir()) / 'links'
    LN_DIR.mkdir(exist_ok=True)

    data = {'counter': 0}
    version = current_version()
    print("Linking all modules into: {}".format(LN_DIR))
    valid_modules = []

    [x.unlink() for x in LN_DIR.glob("*")]
    os.system("chown $ODOO_USER:$ODOO_USER \"{}\"".format(LN_DIR)) # TODO in pathlib

    def search_dir_for_modules(base_dir):

        def link_module(module):
            if version >= 11.0:
                module_name = module.name
                target = LN_DIR / module_name
                if target.is_symlink():
                    if target.resolve() != module.path.resolve():
                        # let override OCA modules
                        print("Overriding module {} in {} by {}".format(module.name, target.resolve(), module.path))
                        target.unlink()
                rel_path = Path(".." / module.path.relative_to(customs_dir()))
                target.symlink_to(rel_path, target_is_directory=True)
                data['counter'] += 1

            else:
                # pruefen, obs nicht zu den verbotenen pfaden gehoert:

                target = LN_DIR / module.name

                if target.exists():
                    if target.resolve().absolute() != mod.path.resolve().absolute():
                        # let override OCA modules
                        if "OCA" in target.parts:
                            os.unlink(target)
                        elif "OCA" in mod.path.parts:
                            os.unlink(target)
                        else:
                            raise Exception("Module {} already linked to {}; could not link to {}".format(
                                os.path.basename(target),
                                os.path.realpath(target),
                                mod.path
                            ))

                # if there are versions under the module e.g. 6.1, 7.0 then take name from parent
                try:
                    float(target.name)
                except Exception:
                    pass
                else:
                    raise Exception("not supported anymore: {}".format(str(module.path)))

                if target.is_symlink():
                    target.unlink()

                rel_path = Path(".." / module.path.relative_to(customs_dir()))
                target.symlink_to(rel_path)
                data['counter'] += 1

        # default module paths, can be set by .module_paths
        modules_path_file = customs_dir() / '.module_paths'
        module_paths = [
            'OCA',
            'common',
            'modules',
        ]
        if modules_path_file.exists():
            module_paths = list(filter(lambda x: x, modules_path_file.read_text().split("\n")))
        del modules_path_file
        _customs_dir = customs_dir()

        for file in Path(base_dir).glob("**/" + MANIFEST_FILE):
            if not any(str(file.relative_to(_customs_dir)).startswith(x + "/") for x in module_paths):
                continue
            try:
                mod = Module(file)
            except Module.IsNot:
                continue
            if not mod.in_version:
                continue

            valid_modules.append(mod)

        def _sort_modules(mod):
            for i, x in enumerate(module_paths):
                if x in str(mod.path.relative_to(_customs_dir)):
                    return i
            return 99999999

        for path in sorted(valid_modules, key=_sort_modules):
            link_module(path)

    search_dir_for_modules(customs_dir())
    return data['counter']


def write_debug_instruction(instruction):
    (run_dir() / ODOO_DEBUG_FILE).write_text(instruction)


"""

    # @classmethod

    # def is_module_listed_in_install_file_or_in_dependency_tree(clazz, module):
        # ""
        # Checks wether a module is in the install file. If not,
        # then via the dependency tree it is checked, if it is an ancestor
        # of the installed modules
        # ""
        # depends = clazz.get_module_dependency_tree(module)
        # mods = get_customs_modules()
        # if module in mods:
            # return True

        # def get_parents(module):
            # for parent, dependson in depends.items():
                # if module in dependson:
                    # yield parent

        # def check_module(module):
            # for p in get_parents(module):
                # if p in mods:
                    # return True
                # if check_module(p):
                    # return True
            # return False

        # return check_module(module)
"""
