from packaging.specifiers import SpecifierSet
from packaging.version import Version
from packaging.requirements import Requirement
from packaging import markers

import threading
import arrow
import pprint
import json
import click
from .tools import _is_db_initialized
from . import iscompatible
from pathlib import Path
from copy import deepcopy
import pickle
import os
import shutil
import uuid
from gimera.repo import Repo
from .tools import get_hash, get_git_hash
from .tools import __try_to_set_owner as try_to_set_owner
from .tools import measure_time
from .tools import is_git_clean
from .tools import whoami
from .tools import abort
from .tools import __rmtree as rmtree
from .tools import pretty_xml
from .tools import bashfind
from .tools import __assure_gitignore

try:
    from psycopg2 import IntegrityError
except Exception:
    pass
from .tools import _extract_python_libname
from .tools import _exists_table
from .tools import _execute_sql
from .tools import table_exists
from .tools import measure_time
from .odoo_config import get_conn_autoclose, manifest_file_names
from .odoo_config import current_version
from .odoo_config import get_settings
from .odoo_config import customs_dir
from .odoo_config import translate_path_into_machine_path
from .odoo_config import MANIFEST_FILE
from .odoo_config import manifest_file_names
from .odoo_config import MANIFEST
from .myconfigparser import MyConfigParser
from .odoo_parser import get_view
import fnmatch
import re
import pprint
from lxml import etree
import subprocess

import inspect
import sys

LANG = os.getenv("ODOO_LANG", "de_DE")  # todo from environment


name_cache = {}
remark_about_missing_module_info = set()
dep_tree_cache = {}
Modules_Cache = {}


def module_or_string(module):
    if isinstance(module, str):
        return module
    if isinstance(module, Module):
        return module.name


class NotInAddonsPath(Exception):
    pass


from .tools import exe


def delete_qweb(config, modules):
    with get_conn_autoclose(config) as cr:
        if modules != "all":
            cr.execute("select name from ir_module_module where name = %s", (modules,))
        else:
            cr.execute("select name from ir_module_module; ")

        def erase_view(view_id):
            cr.execute("select id from ir_ui_view where inherit_id = %s;", (view_id,))
            for child_view_id in [x[0] for x in cr.fetchall()]:
                erase_view(child_view_id)
            cr.execute(
                """
            select
                id
            from
                ir_model_data
            where
                model='ir.ui.view' and res_id =%s
            """,
                (view_id,),
            )
            data_ids = [x[0] for x in cr.fetchall()]

            for data_id in data_ids:
                cr.execute("delete from ir_model_data where id = %s", (data_id,))

            sp = "sp" + uuid.uuid4().hex
            cr.execute(f"savepoint {sp}")
            try:
                cr.execute("delete from ir_ui_view where id = %s;", [view_id])
                cr.execute(f"release savepoint {sp}")

            except IntegrityError:
                cr.execute(f"rollback to savepoint {sp}")

        for module in cr.fetchall():
            if not DBModules.is_module_installed(module):
                continue
            cr.execute(
                """
                select
                    res_id
                from
                    ir_model_data
                where
                    module=%s and model='ir.ui.view' and res_id in (select id from ir_ui_view where type='qweb');
            """,
                [module],
            )
            for view_id in [x[0] for x in cr.fetchall()]:
                erase_view(view_id)


def get_all_langs(config):
    sql = "select distinct code from res_lang where active = true;"
    with get_conn_autoclose() as cr:
        cr.execute(sql)
        langs = [x[0] for x in cr.fetchall() if x[0]]
    return langs


def get_modules_from_install_file(include_uninstall=False):
    res = MANIFEST().get("install", [])
    if include_uninstall:
        for mod in MANIFEST().get("uninstall", []):
            try:
                Module.get_by_name(mod)
            except (NotInAddonsPath, Module.IsNot, KeyError):
                click.secho(
                    f"WARNING: module {mod} cannot be uninstalled - "
                    "not found in source",
                    fg="yellow",
                )
                pass
            else:
                res += [mod]
    return res


class DBModules(object):
    def __init__(self):
        pass

    @classmethod
    def check_if_all_modules_from_install_are_installed(clazz, check_func):
        res = set()
        for module in get_modules_from_install_file():
            if not clazz.is_module_installed(module):
                res.add(module)

        if check_func:
            check_func(res)

        return list(res)

    @classmethod
    def abort_upgrade(clazz):
        SQL = """
            UPDATE ir_module_module SET state = 'installed' WHERE state = 'to upgrade';
            UPDATE ir_module_module SET state = 'uninstalled' WHERE state = 'to install';
        """
        with get_conn_autoclose() as cr:
            if table_exists(cr, "ir_module_module"):
                _execute_sql(cr, SQL)

    @classmethod
    def show_install_state(clazz, raise_error):
        dangling = clazz.get_dangling_modules()
        if dangling:
            print("Displaying dangling modules:")
        for row in dangling:
            print("{}: {}".format(row[0], row[1]))

        if dangling and raise_error:
            raise Exception(
                "Dangling modules detected - please fix installation problems and retry!"
            )

    @classmethod
    def set_uninstallable_uninstalled(clazz):
        with get_conn_autoclose() as cr:
            _execute_sql(
                cr,
                "update ir_module_module set state = 'uninstalled' where state = 'uninstallable';",
            )

    @classmethod
    def get_dangling_modules(clazz):
        with get_conn_autoclose() as cr:
            if not _exists_table(cr, "ir_module_module"):
                return []

            rows = _execute_sql(
                cr,
                sql="SELECT name, state from ir_module_module where state not in ('installed', 'uninstalled', 'uninstallable');",
                fetchall=True,
            )
        return rows

    @classmethod
    def get_outdated_installed_modules(clazz, mods):
        odoo_version = current_version()
        for mod in clazz.get_all_installed_modules():
            if mod not in mods.modules:
                continue
            version_new = mods.modules[mod].manifest_dict.get("version", False)
            if not version_new:
                continue
            if len(list(x for x in version_new if x == ".")) <= 2:
                version_new = str(odoo_version) + "." + version_new
            version = clazz.get_meta_data(mod)["version"]
            if version and version != version_new:
                yield mod

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
        with get_conn_autoclose() as cr:
            if not _exists_table(cr, "ir_module_module"):
                return []
            cr.execute(sql)
            return [x[0] for x in cr.fetchall()]

    @classmethod
    def dangling_modules(clazz):
        with get_conn_autoclose() as cr:
            cr.execute(
                "select count(*) from ir_module_module where state in ('to install', 'to upgrade', 'to remove');"
            )
            return cr.fetchone()[0]

    @classmethod
    def get_all_installed_modules(clazz):
        with get_conn_autoclose() as cr:
            if not _exists_table(cr, "ir_module_module"):
                return []
            cr.execute(
                "select name from ir_module_module where state not in ('uninstalled', 'uninstallable', 'to remove');"
            )
            return [x[0] for x in cr.fetchall()]

    @classmethod
    def get_meta_data(clazz, module):
        with get_conn_autoclose() as cr:
            if not _exists_table(cr, "ir_module_module"):
                return {}
            cr.execute(
                "select id, state, name, latest_version from ir_module_module where name = %s",
                (module,),
            )
            record = cr.fetchone()
            if not record:
                return {
                    "name": module,
                    "state": "uninstalled",
                    "version": False,
                    "id": False,
                }
            return {
                "name": record[2],
                "state": record[1],
                "id": record[0],
                "version": record[3],
            }

    @classmethod
    def get_module_state(clazz, module):
        with get_conn_autoclose() as cr:
            cr.execute(
                "select name, state from ir_module_module where name = %s", (module,)
            )
            state = cr.fetchone()
            if not state:
                return False
            return state[1]

    @classmethod
    def is_module_listed(clazz, module):
        with get_conn_autoclose() as cr:
            if not _exists_table(cr, "ir_module_module"):
                return False
            cr.execute(
                "select count(*) from ir_module_module where name = %s", (module,)
            )
            return bool(cr.fetchone()[0])

    @classmethod
    def is_module_installed(clazz, module, raise_exception_not_initialized=False):
        if not module:
            raise Exception("no module given")
        with get_conn_autoclose() as cr:
            if not _is_db_initialized(cr):
                if raise_exception_not_initialized:
                    raise UserWarning("Database not initialized")
                return False
            cr.execute(
                "select name, state from ir_module_module where name = %s", (module,)
            )
            state = cr.fetchone()
            if not state:
                return False
            return state[1] in ["installed", "to upgrade"]


def make_customs(config, ctx, path, version, odoosh):
    from gimera.gimera import apply as gimera
    from .tools import abort
    import click

    if not path.exists():
        abort("Path does not exist: {}".format(path))
    elif list(path.glob("*")):
        files = [x for x in path.glob("*") if x.name != ".git"]
        if files:
            if not config.force:
                abort("Path is not empty: {}".format(path))

    import inquirer
    from .tools import copy_dir_contents

    dir = get_template_dir()
    src_dir = dir / "customs_template"

    def _floatify(x):
        try:
            return float(x)
        except Exception:
            return 0

    versions = sorted(
        [x.name for x in src_dir.glob("*")], key=lambda x: _floatify(x), reverse=True
    )
    if not version:
        version = inquirer.prompt([inquirer.List("version", "", choices=versions)])[
            "version"
        ]
        del versions

    copy_dir_contents(src_dir / version, path)

    manifest_file = path / "MANIFEST"
    manifest = eval(manifest_file.read_text())

    if not (path / ".git").exists():
        subprocess.call(["git", "init"], cwd=path)
    for repo in ["odoo", "enterprise", "themes"]:
        __assure_gitignore(path / ".gitignore", "/" + repo + "/")
    subprocess.call(["git", "add", "."], cwd=path)
    subprocess.call(["git", "commit", "-am", "init"], cwd=path)
    ctx.invoke(gimera, recursive=True, update=True)
    try_to_set_owner(whoami(), path)
    subprocess.call(["odoo reload"], shell=True, cwd=path)

    click.secho("Initialized - please call following now.", fg="green")
    click.secho("odoo next   (to get a free next port)", fg="green")
    click.secho("odoo -f db reset", fg="green")
    sys.exit(0)


def get_template_dir():
    path = Path(os.path.expanduser("~/.odoo/templates"))
    url = "https://github.com/marcwimmer/wodoo-templates"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        subprocess.check_call(["git", "clone", url, path])
    try:
        subprocess.check_call(["git", "pull"], cwd=path)
    except:
        if path.exists():
            rmtree(None, path)
        subprocess.check_call(["git", "clone", url, path])
    return path


def make_module(parent_path, module_name):
    """
    Creates a new odoo module based on a provided template.

    """
    version = current_version()
    complete_path = Path(parent_path) / Path(module_name)
    del parent_path
    if complete_path.exists():
        raise Exception("Path already exists: {}".format(complete_path))
    odoo_root = os.environ["ODOO_HOME"]

    source = get_template_dir()
    shutil.copytree(str(source / "module_template" / str(version)), complete_path)

    for root, dirs, _files in os.walk(complete_path):
        if ".git" in dirs:
            dirs.remove(".git")
        for filepath in _files:
            filepath = os.path.join(root, filepath)
            with open(filepath, "r") as f:
                content = f.read()
            content = content.replace("___module_name___", module_name)
            with open(filepath, "w") as f:
                f.write(content)

    # enter in install file
    m = MANIFEST()
    modules = m["install"]
    modules.append(module_name)
    m["install"] = modules

    # correct file permissions
    try_to_set_owner(whoami(), complete_path)


def restart(quick):
    if quick:
        write_debug_instruction("quick_restart")
    else:
        write_debug_instruction("restart")


def run_test_file(path):
    if not path:
        instruction = "last_unit_test"
    else:
        instruction = "unit_test:{}".format(path)
    write_debug_instruction(instruction)


def search_qweb(template_name, root_path=None):
    root_path = root_path or os.environ["ODOO_HOME"]
    pattern = "*.xml"
    for path, dirs, _files in os.walk(
        str(root_path.resolve().absolute()), followlinks=True
    ):
        for filename in fnmatch.filter(_files, pattern):
            if filename.name.startswith("."):
                continue
            filename = Path(path) / Path(filename)
            if "static" not in filename.parts:
                continue
            filecontent = filename.read_text()
            for idx, line in enumerate(filecontent.split("\n")):
                for apo in ['"', "'"]:
                    if (
                        "t-name={0}{1}{0}".format(apo, template_name) in line
                        and "t-extend" not in line
                    ):
                        return filename, idx + 1


def update_module(filepath, full=False):
    module = Module(filepath)
    write_debug_instruction(
        "update_module{}:{}".format("_full" if full else "", module.name)
    )


def update_view_in_db_in_debug_file(filepath, lineno):
    write_debug_instruction("update_view_in_db:{}:{}".format(filepath, lineno))


def update_view_in_db(filepath, lineno):
    filepath = translate_path_into_machine_path(filepath)
    module = Module(filepath)
    xml = filepath.read_text().split("\n")

    line = lineno
    xmlid = ""
    while line >= 0 and not xmlid:
        if "<record " in xml[line] or "<template " in xml[line]:
            line2 = line
            while line2 < lineno:
                # with search:
                match = re.findall(r"\ id=[\"\']([^\"^\']*)[\"\']", xml[line2])
                if match:
                    xmlid = match[0]
                    break
                line2 += 1

        line -= 1

    if "." not in xmlid:
        xmlid = module.name + "." + xmlid

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
        if xml and xml[0] and "encoding" in xml[0]:
            _xml = _xml[1:]
        doc = etree.XML("\n".join(_xml))
        for node in doc.xpath(
            "//*[@id='{}' or @id='{}']".format(xmlid, xmlid.split(".")[-1])
        ):
            if node.tag == "record":
                arch = node.xpath("field[@name='arch']")
            elif node.tag == "template":
                arch = [node]
            else:
                raise Exception("impl")

            if arch:
                html = extract_html(arch[0])
                if node.tag == "template":
                    doc = etree.XML(html)
                    datanode = doc.xpath("/data")[0]
                    if node.get("inherit_id", False):
                        datanode.set("inherit_id", node.get("inherit_id"))
                        datanode.set("name", node.get("name", ""))
                    else:
                        datanode.set("t-name", xmlid)
                        datanode.tag = "t"
                    html = etree.tounicode(doc, pretty_print=True)

                # if not inherited from anything, then base tag must not be <data>
                doc = etree.XML(html)
                if not doc.xpath("/data/*[@position] | /*[@position]"):
                    if doc.xpath("/data"):
                        html = etree.tounicode(
                            doc.xpath("/data/*", pretty_print=True)[0]
                        )

                print(html)
                return html

        return None

    if xmlid:
        arch = get_arch()
        if "." in xmlid:
            module, xmlid = xmlid.split(".", 1)
        if arch:
            with get_conn_autoclose() as cr:
                cr.execute(
                    "select column_name from information_schema.columns where table_name = 'ir_ui_view'"
                )
                columns = [x[0] for x in cr.fetchall()]
                arch_column = "arch_db" if "arch_db" in columns else "arch"
                arch_fs_column = "arch_fs" if "arch_fs" in columns else None
                module = Module.get_by_name(module)
                print("Searching view/template for {}.{}".format(module.name, xmlid))
                cr.execute(
                    "select res_id from ir_model_data where model='ir.ui.view' and module=%s and name=%s",
                    [module.name, xmlid],
                )
                res = cr.fetchone()
                if not res:
                    print("No view found for {}.{}".format(module.name, xmlid))
                else:
                    print("updating view of xmlid: %s.%s" % (module.name, xmlid))
                    view_ids = [res[0]]
                    cr.execute(
                        "select type, name from ir_ui_view where id in %s",
                        (tuple(view_ids),),
                    )
                    view_type, view_name = cr.fetchone()

                    version = current_version()
                    if version <= 15.0:
                        if view_type == "qweb":
                            cr.execute(
                                "select id from ir_ui_view where type ='qweb' and name = %s",
                                (view_name,),
                            )
                            view_ids = set(cr.fetchall())

                        cr.execute(
                            "update ir_ui_view set {}=%s where id in %s".format(
                                arch_column
                            ),
                            [arch, tuple(view_ids)],
                        )
                        cr.connection.commit()
                        if arch_fs_column:
                            try:
                                rel_path = (
                                    module.name
                                    + "/"
                                    + str(filepath.relative_to(module.path))
                                )
                                cr.execute(
                                    "update ir_ui_view set arch_fs=%s where id in %s",
                                    [
                                        rel_path,
                                        tuple(view_ids),
                                    ],
                                )
                                cr.connection.commit()
                            except Exception:
                                cr.connection.rollback()

                    if res:
                        exe("ir.ui.view", "write", view_ids, {"arch_db": arch})


def _get_addons_paths():
    from .odoo_config import get_odoo_addons_paths
    config = getattr(threading.currentThread(), "config", None)
    if not config:
        paths = os.getenv("ADDITIONAL_ADDONS_PATHS", "")
    else:
        paths = config.ADDITIONAL_ADDONS_PATHS or ""
    paths = list(filter(bool, map(lambda x: x.strip(), paths.split(","))))
    return get_odoo_addons_paths(additional_addons_paths=paths)


class Modules(object):
    def __init__(self):
        pass

    @property
    def modules(self):
        if "modules" not in Modules_Cache:
            modules = self._get_modules()
            Modules_Cache["modules"] = modules
        return Modules_Cache["modules"]

    @classmethod
    # @profile
    def _get_modules(self, no_deptree=False):
        modnames = set()

        @measure_time
        def get_all_manifests():
            """
            Returns a list of full paths of all manifests
            """
            for path in reversed(_get_addons_paths()):
                mans = bashfind(path, name=manifest_file_names(), maxdepth=2)
                for file in sorted(mans):
                    modname = file.parent.name
                    if modname in modnames:
                        continue
                    modnames.add(file.absolute())
                    yield file.absolute()

        modules = {}
        all_manifests = get_all_manifests()
        for m in list(all_manifests):
            module = Module(m)
            module.manifest_dict.get("just read manifest")
            modules[m.parent.name] = module

        if not no_deptree:
            for module in sorted(set(modules.values())):
                self.get_module_flat_dependency_tree(module=module)

        # if directory is clear, we may cache
        return modules

    def get_changed_modules(self, sha_start):
        filepaths = (
            subprocess.check_output(
                [
                    "git",
                    "diff",
                    f"{sha_start}..HEAD",
                    "--name-only",
                ]
            )
            .decode("utf-8")
            .split("\n")
        )
        modules = []
        root = Path(os.getcwd())
        for filepath in filepaths:
            filepath = root / filepath
            try:
                module = Module(filepath)
            except Module.IsNot:
                pass
            else:
                modules.append(module.name)

    # @profile
    def get_customs_modules(self, mode=None, include_uninstall=False):
        """
        Called by odoo update

        - fetches to be installed modules from install-file
        - selects all installed, to_be_installed, to_upgrade modules from db and checks wether
            they are from "us" or OCA
            (often those modules are forgotten to be updated)

        """
        assert mode in [None, "to_update", "to_install"]

        modules = get_modules_from_install_file(include_uninstall=include_uninstall)

        if mode == "to_install":
            modules = [x for x in modules if not DBModules.is_module_installed(x)]

        modules = list(map(lambda x: Module.get_by_name(x), modules))
        return modules

    @classmethod
    def _get_module_dependency_tree(cls, module):
        """
        Dict of dicts

        'stock_prod_lot_unique': {
            'stock': {
                'base':
            },
            'product': {},
        }
        """

        def append_deps(mod, depth):
            result = set()
            if depth > 1000:
                raise Exception("Recursive loop perhaps - to depth")
            if not mod.exists:
                return set()
            for dep in list(mod.manifest_dict.get("depends", [])):
                if dep == "base":
                    if module.name != "base":
                        result.add(Module.get_by_name("base", no_deptree=True))
                    continue
                try:
                    dep_mod = Module.get_by_name(dep, no_deptree=True)
                except (NotInAddonsPath, Module.IsNot, KeyError):
                    # if it is a module, which is probably just auto install
                    # but not in the manifest, then it is not critical
                    if dep not in remark_about_missing_module_info:
                        remark_about_missing_module_info.add(dep)
                        click.secho(
                            (
                                f"Module not found at resolving dependencies: {dep}"
                                ". Not necessarily a problem at auto install modules."
                            ),
                            fg="blue",
                            bold=False,
                        )
                    dep_mod = Module(None, force_name=dep)

                result.add(dep_mod)
                if dep_mod in dep_tree_cache:
                    result |= set(dep_tree_cache[dep_mod])
                    continue

                result |= append_deps(dep_mod, depth + 1)

            dep_tree_cache[mod] = result
            return result

        if module._dep_tree is None:
            deps = list(sorted(append_deps(module, depth=0)))
            module._dep_tree = deps
        return module._dep_tree

    def get_all_modules_installed_by_manifest(self, additional_modules=None):
        all_modules = set()
        for module in MANIFEST().get("install", []) + (additional_modules or []):
            all_modules.add(module)
            module = Module.get_by_name(module)
            for module2 in self.get_module_flat_dependency_tree(module):
                all_modules.add(module2.name)

        all_auto_installed_modules = self.get_all_auto_install_modules()
        while True:
            len_modules = len(all_modules)
            for auto_install_module in all_auto_installed_modules:
                for module2 in self.get_module_flat_dependency_tree(
                    auto_install_module
                ):
                    # not sufficient: if depending on auto_install module
                    # for module2 in auto_install_module.manifest_dict['depends']:
                    if module2.name not in all_modules:
                        break
                else:
                    all_modules.add(auto_install_module.name)
            if len_modules == len(all_modules):
                break
        return list(all_modules)

    @classmethod
    def get_module_flat_dependency_tree(self, module):
        deps = self._get_module_dependency_tree(module)
        return sorted(list(deps))

    def get_all_auto_install_modules(self):
        auto_install_modules = []
        for module in sorted(Modules().modules):
            try:
                module = Module.get_by_name(module)
            except NotInAddonsPath:
                continue
            if module.manifest_dict.get("auto_install", False):
                auto_install_modules.append(module)
        return list(sorted(set(auto_install_modules)))

    # @profile
    def get_filtered_auto_install_modules_based_on_module_list(self, module_list):
        def _transform_modulelist(module_list):
            for mod in module_list:
                try:
                    objmod = Module.get_by_name(mod)
                    yield objmod
                except NotInAddonsPath:
                    pass

        module_list = list(_transform_modulelist(module_list))

        complete_modules = set()
        for mod in module_list:
            complete_modules |= set(list(self.get_module_flat_dependency_tree(mod)))

        def _get(all_modules):
            for auto_install_module in all_modules:
                dependencies = set(
                    list(self.get_module_flat_dependency_tree(auto_install_module))
                )
                installed_dependencies = set(
                    [
                        x
                        for x in sorted(dependencies)
                        if x.exists
                        if x.manifest_dict.get("auto_install") or x in complete_modules
                    ]
                )
                if dependencies == installed_dependencies:
                    yield auto_install_module

                    if all(x in module_list for x in dependencies):
                        yield auto_install_module

        modules = list(sorted(self.get_all_auto_install_modules()))
        while True:
            before = list(sorted(set(map(lambda x: x.name, modules))))
            modules = list(_get(modules))
            after = list(sorted(set(map(lambda x: x.name, modules))))
            if after == before:
                break
        return list(sorted(set(modules)))

    # @profile
    def get_all_used_modules(self, include_uninstall=False):
        """
        Returns all modules that are directly or indirectly
        (auto install, depends) installed.
        """
        result = set()
        modules = self.get_customs_modules(include_uninstall=True)
        auto_install_modules = (
            self.get_filtered_auto_install_modules_based_on_module_list(modules)
        )
        modules += auto_install_modules

        for module in modules:
            result.add(module.name)
            dependencies = self.get_module_flat_dependency_tree(module)
            for dep in dependencies:
                result.add(dep)

        return list(result)

    def get_all_external_dependencies(self, modules, python_version):
        global_data = {"pip": []}
        for module_name in modules:
            module = Module.get_by_name(module_name)
            if module.path is None:
                raise Exception(f"Module has no path: {module_name}")
            file = module.path / "external_dependencies.txt"

            def extract_deps(data):
                if not data:
                    return
                to_add = data.get("python", [])
                global_data["pip"].extend(data.get("pip", to_add))
                for k, v in data.items():
                    if k not in ["pip", "python"]:
                        global_data.setdefault(k, []).extend(v)

            if file.exists():
                try:
                    content = json.loads(file.read_text())
                except Exception as e:
                    click.secho("Error parsing json in\n{file}:\n{e}", fg="red")
                    click.secho(file.read_text(), fg="red")
                    sys.exit(1)
                extract_deps(content)
            else:
                extract_deps(module.manifest_dict.get("external_dependencies", {}))

        global_data["pip"] = self.resolve_pydeps(
            set(global_data["pip"]), python_version
        )
        return global_data

    def _filter_requirements(self, pydeps, python_version):
        assert isinstance(python_version, tuple)
        str_python_version = ".".join(map(str, python_version[:2]))
        environment = {
            "python_version": str_python_version,
            "sys_platform": sys.platform,
        }

        # keep highest version and or leaveout loosers
        def _filter(x):
            if not x:
                return
            if "@" in x:
                # concrete url like "pymssql@git+https://github.com/marcwimmer/pymssql"
                return x
            x = x.split("#")[0].strip()
            if not x:
                return
            for extra in x.split(";")[1:]:
                expr = markers.Marker(extra)
                res = expr.evaluate(environment)
                if not res:
                    return
            return STRIP(x)

        def STRIP(dep):
            res = dep.split("#")[0].split(";")[0].strip()
            if res.endswith(".*"):
                # xlwt==1.3.*
                res = res[:-2]
            return res

        def _make_tuples(dep):
            libname = _extract_python_libname(dep)
            if not libname:
                return []
            try:
                reqs = iscompatible.parse_requirements(dep)
            except Exception as ex:
                raise
            reqs = list(reqs)
            if reqs:
                for i in range(len(reqs)):
                    try:
                        reqs[i] = list(reqs[i])
                        reqs[i][1] = iscompatible.string_to_tuple(reqs[i][1])
                    except:
                        raise
            return libname, tuple(reqs)

        reqs = {}
        for dep in list(filter(_filter, pydeps)):
            dep = STRIP(dep)
            print(dep)
            libname, version = _make_tuples(dep)
            reqs.setdefault(libname, []).append(version)
        """
        parsed_requirements ilike
        [
        ('>=', '1.0.0'),
        ('>=', '1.2.0')
        ]
        """
        return reqs

    def _pydeps_filter_best_fit(self, pydeps):
        result = set()
        allowed = ["==", ">="]
        unallowed = [
            x for x in pydeps if not isinstance(x, str) and x[1][0] not in allowed
        ]
        if unallowed:
            raise Exception(f"Unhandled: {unallowed} - only {allowed} allowed")

        for libname in pydeps.keys():
            # mixed == and >=
            reqs = pydeps.get(libname, [])

            # handle case: reqs = [()]
            unspecific_ones = [x for x in reqs if not x]
            if len(unspecific_ones) == len(reqs):
                result.add(libname)
                continue
            reqs = [x for x in reqs if x]

            ge = sorted([x for x in reqs if x[0] == ">="], key=lambda x: x[1])
            gt = sorted(
                [x for x in reqs if x[0] == ">"], key=lambda x: x[1]
            )  # very unusual, not seen yet
            eq = [x for x in reqs if x[0] == "=="]
            no = [x for x in reqs if not x]

            if ge or eq and no:
                no = []

            if eq and len(eq) > 1 and not all(x[1] == eq[0][1] for x in eq):
                click.secho(
                    f"Dependency conflict: {libname} {eq[0]} - {eq[1:]}", fg="red"
                )
                sys.exit(-1)

            if eq and ge:
                if eq[-1][1] < ge[-1][1]:
                    click.secho(
                        f"Dependency conflict: {libname} {ge[0]} - {eq[0]}", fg="red"
                    )
                    sys.exit(-1)

            if gt:
                raise NotImplementedError("gt")

            if eq:
                result.add(f"{libname}{eq[-1][0]}{'.'.join(map(str, eq[-1][1]))}")
            elif ge:
                result.add(f"{libname}{ge[-1][0]}{'.'.join(map(str, ge[-1][1]))}")
            else:
                if len(reqs) == 1:
                    result.add(
                        f"{libname}{reqs[0][-1][0]}{'.'.join(map(str, reqs[0][-1][1]))}"
                    )
                else:
                    result.add(libname)
        return list(sorted(result))

    def resolve_pydeps(self, pydeps, python_version):
        pydeps = list(set(pydeps))

        parsed_requirements = self._filter_requirements(pydeps, python_version)
        result = self._pydeps_filter_best_fit(parsed_requirements)

        return list(result)


class Module(object):
    assets_template = """
    <odoo><data>
    <template id="{id}" inherit_id="{inherit_id}">
        <xpath expr="." position="inside">
        </xpath>
    </template>
    </data>
    </odoo>
    """

    class IsNot(Exception):
        pass

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"{self.name}"

    def __add__(self, other):
        return self.name + other

    def __lt__(self, other):
        if isinstance(other, str):
            return self.name < other
        return self.name < other.name

    def __gt__(self, other):
        if isinstance(other, str):
            return self.name > other
        return self.name > other.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        return self.name == other.name and self.path == other.path

    def __hash__(self):
        try:
            path = self.path
            name = self.name
            return hash(f"Module_{path}_{name}")
        except RecursionError:
            raise Exception(f"Recursion at {self.name}")

    def __init__(self, path, force_name=None):
        self.version = float(current_version())
        self._manifest_dict = None
        self._manifest_path = None
        self._dep_tree = None
        if path:
            self.__init_path(path, manifest_file_names())
            self.path = self._manifest_path.parent
        else:
            self.path = None

        if force_name:
            self.name = force_name
        else:
            self.name = self._manifest_path.parent.name

    @property
    def descendants(self):
        res = []
        mods = Modules()
        modules = mods.get_all_modules_installed_by_manifest()
        all_modules = [self.get_by_name(x) for x in modules]
        for check in all_modules:
            if self.name in [
                x.name for x in mods.get_module_flat_dependency_tree(check)
            ]:
                res.append(check)
        return res

    @property
    def is_customs(self):
        return self.path.parts[0] not in ["odoo", "enterprise", "themes"]

    @property
    def exists(self):
        return bool(self.path)

    def __init_path(self, path, manifest_filename):
        path = Path(path)
        _customs_dir = customs_dir()

        remember_cwd = os.getcwd()
        try:
            cwd = Path(remember_cwd)
            if str(path).startswith("/"):
                try:
                    path = path.relative_to(_customs_dir)
                    os.chdir(_customs_dir)
                except Exception:
                    try:
                        path = path.relative_to(cwd)
                    except ValueError:
                        path = path.relative_to(_customs_dir)
                        os.chdir(
                            _customs_dir
                        )  # reset later; required that parents works
            p = path if path.is_dir() else path.parent

            for p in [p] + list(p.parents):
                if (p / manifest_filename).exists():
                    if ".git" in p.parts:
                        continue
                    self._manifest_path = p / manifest_filename
                    break
            if not getattr(self, "_manifest_path", ""):
                raise Module.IsNot((f"no module found for {path}"))
        finally:
            os.chdir(remember_cwd)

    @property
    def manifest_path(self):
        return self._manifest_path

    @property
    def manifest_dict(self):
        if not self._manifest_dict:
            try:
                if not self.manifest_path:
                    abort(f"Could not find manifest path for {self.name}")
                path = customs_dir() / self.manifest_path
                content = path.read_text()
                content = "\n".join(
                    filter(
                        lambda x: not x.strip().startswith("#"), content.splitlines()
                    )
                )
                self._manifest_dict = eval(content)  # TODO safe

            except (SyntaxError, Exception) as e:
                abort(f"error at file: {self.manifest_path}:\n{str(e)}")
        return self._manifest_dict

    def __make_path_relative(self, path):
        path = path.resolve().absolute()
        path = path.relative_to(self.path)
        if not path:
            raise Exception("not part of module")
        return self.path.name / path

    def apply_po_file(self, pofile_path):
        """
        pofile_path - pathin in the machine
        """
        pofile_path = self.__make_path_relative(pofile_path)
        lang = pofile_path.name.split(".po")[0]
        write_debug_instruction("import_i18n:{}:{}".format(lang, pofile_path))

    def export_lang(self, current_file, lang):
        write_debug_instruction("export_i18n:{}:{}".format(lang, self.name))

    @property
    def hash(self):
        from .tools import get_directory_hash

        return get_directory_hash(self.path)

    @classmethod
    def __get_by_name_cached(cls, name, nocache=False, no_deptree=False):
        if name not in name_cache:
            name_cache.setdefault(
                name, cls._get_by_name(name, nocache=nocache, no_deptree=no_deptree)
            )
        return name_cache[name]

    @classmethod
    def get_by_name(cls, name, nocache=False, no_deptree=False):
        if isinstance(name, Module):
            return name
        mod = cls.__get_by_name_cached(name, nocache=nocache, no_deptree=no_deptree)
        return mod

    @classmethod
    def _get_by_name(cls, name, nocache=False, no_deptree=False):

        if isinstance(name, Module):
            name = name.name
        path = None
        for addon_path in _get_addons_paths():
            dir = addon_path / name
            if dir.exists():
                path = dir
            del dir
        if not path:
            possible_matches = bashfind(".", name=name, type="d")
            if possible_matches:
                click.secho("Found the missing module here:", fg="yellow", bold=True)
                for dir in possible_matches:
                    click.secho(dir, fg="yellow")
                click.secho("Please add it to the manifest addons-paths")

            raise NotInAddonsPath(f"Could not get path for {name}")
        if path.exists():
            path = path.resolve()

        if path.is_dir():
            try:
                return Module(path)
            except Module.IsNot:
                # perhaps empty dir
                pass

        # could be an odoo module then
        for path in _get_addons_paths():
            if (path / name).resolve().is_dir():
                try:
                    return Module(path / name)
                except Module.IsNot:
                    pass
        raise KeyError(f"Module not found or not linked: {name}")

    @property
    def dependent_modules(self):
        """
        per modulename all dependencies - no hierarchy
        """
        result = {}
        for dep in self.manifest_dict.get("depends", []):
            result.add(Module.get_by_name(dep))

        return result

    def get_lang_file(self, lang):
        lang_file = (self.path / "i18n" / lang).with_suffix(".po")
        if lang_file.exists():
            return lang_file

    @property
    def in_version(self):
        if self.version >= 10.0:
            try:
                version = self.manifest_dict.get("version", "")
            except SyntaxError:
                return False
            # enterprise modules from odoo have versions: "", "1.0" and so on... ok
            if not version:
                return True
            if len(version.split(".")) <= 3:
                # allow 1.0 2.2 etc.
                return True
            check = str(self.version).split(".")[0] + "."
            return version.startswith(check)
        else:
            info_file = self.path / ".ln"
            if info_file.exists():
                info = eval(info_file.read_text())
                if isinstance(info, (float, int)):
                    min_ver = info
                    max_ver = info
                    info = {"minimum_version": min_ver, "maximum_version": max_ver}
                else:
                    min_ver = info.get("minimum_version", 1.0)
                    max_ver = info.get("maximum_version", 1000.0)
                if min_ver > max_ver:
                    raise Exception("Invalid version: {}".format(self.path))
                if self.version >= float(min_ver) and self.version <= float(max_ver):
                    return True

            elif "OCA" in self.path.parts:
                relpath = str(self.path).split("/OCA/")[1].split("/")
                return len(relpath) == 2
        return False

    def update_assets_file(self):
        """
        Put somewhere in the file: assets: <xmlid>, then
        asset is put there.
        """
        DEFAULT_ASSETS = "web.assets_backend"

        def default_dict():
            return {
                "stylesheets": [],
                "js": [],
            }

        files_per_assets = {}
        # try to keep assets id
        filepath = self.path / "views/assets.xml"
        current_id = None
        if filepath.exists():
            with filepath.open("rb") as f:
                xml = f.read()
                doc = etree.XML(xml)
                for t in doc.xpath("//template/@inherit_id"):
                    current_id = t

        all_files = self.get_all_files_of_module()
        if current_version() < 11.0:
            module_path = Path(
                str(self.path).replace("/{}/".format(current_version()), "")
            )
            if str(module_path).endswith("/{}".format(current_version())):
                module_path = "/".join(str(module_path).split("/")[:-1])

        prefix_static = f"/{self.name}/"
        for local_file_path in all_files:
            if local_file_path.name.startswith("."):
                continue

            if current_id:
                parent = current_id
            elif "static" in local_file_path.parts:
                parent = DEFAULT_ASSETS
            elif (
                "report" in local_file_path.parts or "reports" in local_file_path.parts
            ):
                parent = "web.report_assets_common"
            else:
                continue
            files_per_assets.setdefault(parent, default_dict())

            url = prefix_static + str(local_file_path)
            if local_file_path.suffix in [".less", ".css", ".scss"]:
                files_per_assets[parent]["stylesheets"].append(url)
            elif local_file_path.suffix in [".js"]:
                files_per_assets[parent]["js"].append(url)
            del local_file_path
            del url

        doc = etree.XML(Module.assets_template)
        for asset_inherit_id, _files in files_per_assets.items():
            parent = deepcopy(doc.xpath("//template")[0])
            parent.set("inherit_id", asset_inherit_id)
            parent.set("id", asset_inherit_id.split(".")[-1])
            parent_xpath = parent.xpath("xpath")[0]
            for style in _files["stylesheets"]:
                etree.SubElement(
                    parent_xpath,
                    "link",
                    {
                        "rel": "stylesheet",
                        "href": str(style),
                    },
                )
            for js in _files["js"]:
                etree.SubElement(
                    parent_xpath,
                    "script",
                    {
                        "type": "text/javascript",
                        "src": str(js),
                    },
                )
            doc.xpath("/odoo/data")[0].append(parent)

        # remove empty assets and the first template template
        for to_remove in doc.xpath("//template[1] | //template[xpath[not(*)]]"):
            to_remove.getparent().remove(to_remove)

        if current_version() > 14.0:
            if filepath.exists():
                filepath.unlink()
            manifest = self.path / "__manifest__.py"
            jsoncontent = eval(manifest.read_text())
            jsoncontent.setdefault("assets", {})
            existing_files = []
            for asset_file in jsoncontent.get("assets", []):
                for file in jsoncontent["assets"][asset_file]:
                    existing_files.append(file)
            for asset_name, files in files_per_assets.items():
                jsoncontent["assets"].setdefault(asset_name, [])
                for files in files.values():
                    for file in files:
                        file = file.lstrip("/")
                        if file in existing_files:
                            continue
                        if file not in jsoncontent["assets"][asset_name]:
                            jsoncontent["assets"][asset_name].append(file)
                        del file
            self.write_manifest(jsoncontent)
        else:
            if not doc.xpath("//link| //script"):
                if filepath.exists():
                    filepath.unlink()
            else:
                filepath.parent.mkdir(exist_ok=True)
                filepath.write_bytes(pretty_xml(etree.tostring(doc, pretty_print=True)))

    def get_all_files_of_module(self):
        for file in self.path.glob("**/*"):
            file = file.relative_to(self.path)
            if file.name.startswith("."):
                continue
            if ".git" in file.parts:
                continue
            if file.parts[0].startswith("."):
                continue
            # relative to module path
            yield file

    def update_init_imports(self):
        def _remove_all_instruction(content):
            if "__all__ =" not in content:
                return content
            content = content.replace("import os", "")
            content = content.replace("import glob", "")
            content = (
                "\n".join(
                    filter(lambda x: "__all__ =" not in x, content.splitlines())
                ).strip()
                + "\n"
            )
            return content

        for path in self.path.glob("*"):
            if not path.is_dir():
                continue
            if path.name not in ["models", "tests", "controller", "controllers"]:
                continue
            init_file = path / "__init__.py"
            if not init_file.exists():
                continue
            content = _remove_all_instruction(init_file.read_text()).splitlines()

            for file in path.glob("*"):
                if file.suffix == ".py" and file.stem not in ["__init__"]:
                    importinstruction = f"from . import {file.stem}"
                    if importinstruction not in content:
                        content += [importinstruction]

            # remove if py does not exist anymore:
            for line in list(content):
                if line.startswith("from . import "):
                    if not (path / (line.split(" ")[-1] + ".py")).exists():
                        content.remove(line)

            init_file.write_text("\n".join(content))

    def update_module_file(self):
        # updates __openerp__.py the update-section to point to all xml files
        # in the module; # except if there is a directory test; those files are ignored;
        self.update_assets_file()
        self.update_init_imports()
        mod = self.manifest_dict

        all_files = list(self.get_all_files_of_module())
        # first collect all xml files and ignore test and static
        DATA_NAME = "data"
        if current_version() <= 7.0:
            DATA_NAME = "update_xml"

        mod[DATA_NAME] = []
        mod["demo"] = []
        mod["qweb"] = []
        if current_version() < 14.0:
            mod["css"] = []
        is_web = False

        for local_path in all_files:
            if "test" in local_path.parts:
                continue
            if local_path.suffix in [".xml", ".csv", ".yml"]:
                if "demo" in local_path.parts:
                    mod["demo"].append(str(local_path))
                elif "static" in local_path.parts:
                    # contains qweb file
                    is_web = True
                    if local_path.suffix == ".xml":
                        if "qweb" in mod:
                            if str(local_path) not in mod["qweb"]:
                                if current_version() <= 14.0:
                                    mod["qweb"].append(str(local_path))
                                else:
                                    mod["qweb"].append(
                                        self.name + "/" + str(local_path)
                                    )
                else:
                    if local_path.name not in ["gimera.yml"]:
                        mod[DATA_NAME].append(str(local_path))
            elif local_path.suffix == ".js":
                pass
            elif local_path.suffix in [".css", ".less", ".scss"]:
                if "css" in mod:
                    mod["css"] = list(set(mod["css"] + [str(local_path)]))

        # keep test empty: use concrete call to test-file instead of testing
        # on every module update
        mod["test"] = []

        # sort
        mod[DATA_NAME].sort()
        if mod.get("css"):
            mod["css"].sort()
        if "depends" in mod:
            mod["depends"].sort()

        if current_version() > 14.0:
            if "qweb" in mod:
                mod.setdefault("assets", {})
                if current_version() == 15.0:
                    key = "web.assets_qweb"
                else:
                    key = "web.assets_backend"
                mod["assets"].setdefault(key, [])
                mod["assets"][key] += mod.pop("qweb")
                mod["assets"][key] = list(sorted(set(mod["assets"][key])))

        # now sort again by inspecting file content - if __openerp__.sequence NUMBER is found, then
        # set this index; reason: some times there are wizards that reference forms and vice versa
        # but cannot find action ids
        # 06.05.2014: put the ir.model.acces.csv always at the end, because it references others, but security/groups always in front
        sorted_by_index = []  # contains tuples (index, filename)
        for filename in mod[DATA_NAME]:
            filename_xml = filename
            filename = self.path / filename
            sequence = 0
            with filename.open("r") as f:
                content = f.read()
                if "__openerp__.sequence" in content:
                    sequence = int(
                        re.search(r"__openerp__.sequence[^\d]*(\d*)", content).group(1)
                    )
                elif "odoo.sequence" in content:
                    sequence = int(
                        re.search(r"odoo.sequence[^\d]*(\d*)", content).group(1)
                    )
                elif filename.name == "menu.xml":
                    sequence = 1000
                elif filename.name == "groups.xml":
                    sequence = -999999
                elif filename.name == "ir.model.access.csv":
                    sequence = 999999
            sorted_by_index.append((sequence, filename_xml))

        sorted_by_index = sorted(sorted_by_index, key=lambda x: x[0])
        mod[DATA_NAME] = [x[1] for x in sorted_by_index]

        # remove assets.xml for newer versions
        if current_version() > 14.0:
            mod[DATA_NAME] = list(
                filter(lambda x: not x.endswith("/assets.xml"), mod[DATA_NAME])
            )

        if is_web:
            mod["web"] = True
        if "application" not in mod:
            mod["application"] = False

        self.write_manifest(mod)

    def write_manifest(self, data):
        from black import format_str, FileMode

        data = str(data)
        data = format_str(data, mode=FileMode())
        self.manifest_path.write_text(data)

    def calc_complexity(self):
        """
        Calculates the complexity of the module
        """
        res = {"loc": 0}
        for file in self.get_all_files_of_module():
            if file.suffix in [".py", ".csv", ".xml"]:
                file = self.path / file
                res["loc"] += len(file.read_text().splitlines())
        return res


def write_debug_instruction(instruction):
    (customs_dir() / ".debug").write_text(instruction)


def _resolve_path_mapping(conn, path, model):
    """
    Gets the content of related="..." and returns the final model and field
    """
    # last item is field
    splitted = path.split(".")
    for i in range(len(splitted) - 1):
        part = splitted[i]
        sql = f"select id, model, related, relation from ir_model_fields where name = '{part}' and model='{model}'"
        fieldrecord = _execute_sql(conn, sql, fetchone=True)
        if not fieldrecord:
            raise Exception(f"Could not resolve: {path} on {model}")
        id, model, related, relation = fieldrecord
        if related:
            # hardcore; a field part could point to a related item again
            model, part = _resolve_path_mapping(conn, related, model)
        else:
            model = relation

    return model, splitted[-1]


def _determine_affected_modules_for_ir_field_and_related(config, fieldname, modelname):
    """
    removes entry from ir.model.fields and also related entries
    """
    affected_modules = []
    # as destructive:
    assert config.DEVMODE, "Devmode required for this function. May destroy data."
    conn = config.get_odoo_conn()

    def _get_model_for_field(model, fieldname):
        name = f"field_{model.replace('.', '_')}__{fieldname}"
        sql = f"select module from ir_model_data where model='ir.model.fields' and name='{name}'"
        ir_model_data = _execute_sql(conn, sql, fetchone=True)
        if ir_model_data:
            return ir_model_data[0]

    sql = f"select id, model, related from ir_model_fields where related like '%.{fieldname}'"
    related_fields = _execute_sql(conn, sql, fetchall=True)

    for related_field in related_fields:
        id, model, path = related_field

        resolved_model, resolved_fieldname = _resolve_path_mapping(conn, path, model)
        if resolved_model == modelname and resolved_fieldname == fieldname:
            affected_modules.append(
                _get_model_for_field(resolved_model, resolved_fieldname)
            )
    module_of_field = _get_model_for_field(modelname, fieldname)
    if module_of_field:
        affected_modules.append(module_of_field)
    return affected_modules
