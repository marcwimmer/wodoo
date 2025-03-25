import time
from pathlib import Path
from queue import Queue
import threading
import json
import yaml
import shutil
import subprocess
from datetime import datetime
import os
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .odoo_config import customs_dir
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import abort
from .tools import bashfind
from .tools import cwd
from .tools import _get_xml_id
from .tools import pretty_xml
from .tools import _execute_sql
from .tools import odoorpc
from .tools import _output_clipboard_csv


ADDONS_OCA = "addons_OCA"


@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass


def _find_duplicate_modules():
    from .module_tools import Modules

    modules = Modules()
    all_modules = modules.get_all_modules_installed_by_manifest()
    _identify_duplicate_modules(all_modules)


def _apply_gimera_if_required(
    ctx, path, content, force_do=False, no_fetch=None
):
    from gimera.gimera import apply as gimera

    with cwd(path):
        for repo in content["repos"]:
            repo_path = path / repo["path"]
            if (
                repo["type"] == "submodule"
                or force_do
                or not repo_path.exists()
            ):
                ctx.invoke(
                    gimera,
                    repos=[repo["path"]],
                    recursive=True,
                    no_patches=True,
                    non_interactive=True,
                    no_auto_commit=True,
                )
                changed = True
        else:
            changed = False

        if changed:
            click.secho(
                "Restarting reloading because gimera apply was done",
                fg="yellow",
            )
            Commands.invoke(ctx, "reload", no_apply_gimera=True)

            from .module_tools import Modules

            modules = Modules()
            all_modules = modules.get_all_modules_installed_by_manifest()


@src.command()
@click.pass_context
@click.option("--no-fetch", is_flag=True)
def apply_gimera_if_required(ctx, no_fetch):
    path = customs_dir()
    gimera_file = path / "gimera.yml"
    repos = yaml.safe_load(gimera_file.read_text())
    _apply_gimera_if_required(ctx, path, repos, not no_fetch)


@src.command()
@click.pass_context
@pass_config
def find_duplicate_modules(config, ctx):
    _find_duplicate_modules()


@src.command(name="init", help="Create a new odoo")
@click.argument("path", required=True)
@click.argument("version", required=False)
@click.option("--odoosh", is_flag=True)
@click.pass_context
@pass_config
def init(config, ctx, path, odoosh, version):
    from .module_tools import make_customs

    path = Path(path)
    path = path.absolute()
    if not path.exists():
        path.mkdir(parents=True)
    os.chdir(path)
    make_customs(config, ctx, path, version, odoosh)


@src.command()
@pass_config
@click.option("-n", "--name", required=True)
@click.option("-p", "--parent-path", required=False)
def make_module(config, name, parent_path):
    cwd = parent_path or config.working_dir
    from .module_tools import make_module as _tools_make_module

    _tools_make_module(
        cwd,
        name,
    )


@src.command(name="update-ast")
@click.option("-f", "--filename", required=False)
def update_ast(filename):
    from .odoo_parser import update_cache

    started = datetime.now()
    click.echo("Updating ast - can take about one minute")
    update_cache(filename or None)
    click.echo(
        "Updated ast - took {} seconds".format(
            (datetime.now() - started).seconds
        )
    )


@src.command("goto-inherited")
@click.option("-f", "--filepath", required=True)
@click.option("-l", "--lineno", required=True)
def goto_inherited(filepath, lineno):
    from .odoo_parser import goto_inherited_view

    lineno = int(lineno)
    filepath = customs_dir() / filepath
    lines = filepath.read_text().split("\n")
    filepath, lineno = goto_inherited_view(filepath, lineno, lines)
    if filepath:
        print(f"FILEPATH:{filepath}:{lineno}")


@src.command(name="make-modules", help="Puts all modules in /modules.txt")
@pass_config
def make_modules(config):
    modules = ",".join(MANIFEST()["install"])
    (customs_dir() / "modules.txt").write_text(modules)
    click.secho(f"Updated /modules.txt with: \n\n", fg="yellow")
    click.secho(modules)


@src.command()
@pass_config
def setup_venv(config):
    dir = customs_dir()
    os.chdir(dir)
    venv_dir = dir / ".venv"
    gitignore = dir / ".gitignore"
    if ".venv" not in gitignore.read_text().split("\n"):
        with gitignore.open("a") as f:
            f.write("\n.venv\n")

    subprocess.check_call(["python3", "-m", "venv", venv_dir.absolute()])

    click.secho("Please execute following commands in your shell:", bold=True)
    click.secho("source '{}'".format(venv_dir / "bin" / "activate"))
    click.secho("pip3 install cython")
    click.secho(
        "pip3 install -r https://raw.githubusercontent.com/odoo/odoo/{}/requirements.txt".format(
            current_version()
        )
    )
    requirements1 = (
        Path(__file__).parent.parent
        / "images"
        / "odoo"
        / "config"
        / str(current_version())
        / "requirements.txt"
    )
    click.secho("pip3 install -r {}".format(requirements1))


class OdooShRepo(object):
    class Module(object):
        def __init__(self, path):
            self.path = Path(path)
            if not self.path.exists():
                raise Exception(self.path)
            self.manifest = None
            for mf in ["__manifest__.py", "__openerp__.py"]:
                if (self.path / mf).exists():
                    self.manifest = self.path / mf

        @property
        def manifest_dict(self):
            content = eval(self.manifest.read_text())
            return content

    def __init__(self, version):
        self.envkey = "ODOOSH_REPO"
        if self.envkey not in os.environ.keys():
            abort(
                "Please define ODOOSH_REPO env to point to checked out Ninja-Odoosh."
            )
        self.version = str(version)
        self.root = Path(os.environ["ODOOSH_REPO"])
        self.ocapath = self.root / "OCA"
        if not self.ocapath.exists():
            abort(f"Not found: {self.ocapath}")

    def iterate_all_modules(self, version, path=None):
        path = path or self.ocapath
        for path in bashfind(
            path=self.root, type="d", wholename=f"*/{version}/*"
        ):
            if ".git" in path.parts:
                continue
            if path.parent.name != str(version):
                continue
            module = OdooShRepo.Module(path)
            if module.manifest:
                yield module

    def find_auto_installed_modules(self, current_modules):
        from .module_tools import Modules

        modules = Modules()
        all_modules = modules.get_all_modules_installed_by_manifest(
            current_modules
        )
        for module in self.iterate_all_modules(current_version()):
            manifest = module.manifest_dict
            if manifest.get("auto_install"):
                if all(x in all_modules for x in manifest["depends"]):
                    yield module.path

    def find_dependant_modules(self, modulepath):
        from .module_tools import NotInAddonsPath
        from .module_tools import Module

        module = OdooShRepo.Module(modulepath)
        manifest = module.manifest_dict
        for depends in manifest["depends"]:
            try:
                Module.get_by_name(depends)
            except (KeyError, NotInAddonsPath):
                paths = self.find_module(depends)
                if not paths:
                    raise Exception(f"Could not find dependency: {depends}")
                yield paths

    def find_module(self, modulename, ttype="OCA", exact_match=True):
        pass

        if not exact_match:
            modulename = f"*{modulename}*"

        results = []
        if not exact_match:
            modulename = f"*{modulename}*"

        for match in bashfind(path=self.root, type="d", name=modulename):
            if not (match / "__manifest__.py").exists():
                continue
            if match.parent.name != self.version:
                continue
            results.append(match)
            if exact_match:
                return match
        if exact_match:
            raise KeyError(modulename)
        return results


def _get_available_oca_modules(ctx, param, incomplete):
    sh = OdooShRepo(current_version())
    modules = sh.find_module(incomplete, exact_match=False)
    matches = [str(x) for x in sorted(set([x.name for x in modules]))]
    if incomplete:
        matches = matches[:10]
    return matches


@src.command()
@click.pass_context
@pass_config
def rewrite_manifest(config, ctx):
    manifest = MANIFEST()
    manifest.rewrite()


@src.command(
    help="Fetches OCA modules from odoo.sh ninja mentioned in MANIFEST"
)
@click.argument(
    "module",
    nargs=-1,
    shell_complete=_get_available_oca_modules,
    required=True,
)
@click.pass_context
@pass_config
def fetch_modules(config, ctx, module):
    """
    Fetches from odoo-ninjas/odoo.sh
    """
    manifest = MANIFEST()

    from .tools import rsync
    from .odoo_config import customs_dir
    from .module_tools import Modules

    modules = Modules()
    odoosh = OdooShRepo(current_version())

    def transfer_module(module):
        destination = customs_dir() / ADDONS_OCA / module
        if not destination.parent.exists():
            destination.mkdir(exist_ok=True, parents=True)
        if destination.exists():
            shutil.rmtree(destination)
        oca_module = odoosh.find_module(module)
        rsync(oca_module, destination, exclude=[".git"])
        addons_paths = manifest.get("addons_paths", [])
        if not [x for x in addons_paths if x == ADDONS_OCA]:
            addons_paths.append(ADDONS_OCA)
        manifest["addons_paths"] = addons_paths
        manifest["install"] += [module]
        manifest.rewrite()

    for module in module:
        oca_module = odoosh.find_module(module)
        todos = [oca_module.name]
        for dep in odoosh.find_dependant_modules(oca_module):
            todos.append(dep.name)

        for todo in todos:
            transfer_module(todo)

        while True:
            new = list(odoosh.find_auto_installed_modules(todos))
            if not new:
                break
            for todo in new:
                transfer_module(todo)
            todos += new

    _identify_duplicate_modules(todos)


def _identify_duplicate_modules(check):
    # remove duplicate modules or at least identify them:
    from .module_tools import Module

    src = customs_dir()
    ignore_paths = []
    for x in ["odoo", "enterprise", "themes"]:
        ignore_paths.append((src / x).resolve().absolute())

    all_dirs = list(
        filter(
            lambda x: ".git" not in x.parts,
            bashfind(path=src, type="d"),
        )
    )

    for x in sorted(check):
        dirs = filter(lambda dir: dir.name == x, all_dirs)
        for y in dirs:
            if not (y / "__manifest__.py").exists():
                continue
            for ignore_path in ignore_paths:
                try:
                    if y.resolve().absolute().relative_to(ignore_path):
                        break
                except ValueError:
                    continue
            else:
                module = Module.get_by_name(x)
                if (src / y.resolve().absolute()) != (
                    src / module.path.resolve().absolute()
                ):
                    abort(
                        "Found duplicate module, which is a problem for odoo.sh deployment.\n"
                        "Not clear which module gets installed: \n"
                        f"{module.path}\n"
                        f"{y}"
                    )


@src.command(name="pretty-print-manifest")
def pretty_print_manifest():
    from .odoo_config import MANIFEST

    MANIFEST().rewrite()


@src.command()
@pass_config
@click.argument("module")
def security(config, module, model):
    from .module_tools import Modules

    modules = Modules()
    module = modules.get_by_name(module)

    def ensure_secfile():
        header = "model_id:id,group_id:id,id,name,perm_read,perm_write,perm_create,perm_unlink"
        filepath = module.path / "security" / "ir.model.access.csv"
        filepath.parent.mkdir(exist_ok=True)
        if not filepath.read_text():
            filepath.write_text(header + "\n")

    # give rights to choose
    # TODO ...


@src.command()
@click.option("-d", "--dry-run", is_flag=True)
@click.pass_context
@pass_config
def delete_modules_not_in_manifest(config, ctx, dry_run):
    from .module_tools import Modules, Module
    from .odoo_config import customs_dir

    modules = Modules()
    all_modules = modules.modules
    installed_modules = list(sorted(modules.get_all_used_modules()))
    root = customs_dir()

    for mod in all_modules:
        if mod not in installed_modules:
            mod = Module.get_by_name(mod)
            if not any(
                str(mod.path).startswith(X)
                for X in [
                    "odoo",
                    "odoo/odoo",
                    "enterprise",
                    "themes",
                ]
            ):
                click.secho(f"Deleting: {mod.path}", fg="red")
                shutil.rmtree(root / mod.path)


@src.command()
@click.argument("path", required=True)
@click.pass_context
@pass_config
def restore_view(config, ctx, path):
    odoo = odoorpc(config)
    langs = [
        x.code
        for x in odoo.env["res.lang"].browse(odoo.env["res.lang"].search([]))
    ]
    path = Path(path)
    content = path.read_text()
    xmlid = Path(path.name.split(".xmlid.")[1]).stem
    lang = xmlid.split(".lang.")[-1].split(".")[0]
    assert lang in langs
    xmlid = xmlid.split(".lang.")[0]
    module, name = xmlid.split(".")[0], ".".join(xmlid.split(".")[1:])
    data = odoo.env["ir.model.data"].browse(
        odoo.env["ir.model.data"].search(
            [
                ("module", "=", module),
                ("name", "=", name),
                ("model", "=", "ir.ui.view"),
            ]
        )
    )
    view_id = data[0].res_id
    odoo.env["ir.ui.view"].browse(view_id).write(
        {"arch_db": content}, context={"lang": lang, "mickey": "mouse"}
    )
    click.secho(
        f"View [{view_id}] {module}.{name} updated successfully for language {lang}",
        fg="green",
    )


@src.command()
@click.pass_context
@pass_config
def grab_views(config, ctx):
    root = customs_dir() / "src" / "views"
    odoo = odoorpc(config)

    sql = f"select id, name, arch_db, model, priority from ir_ui_view"
    conn = config.get_odoo_conn()
    rows = _execute_sql(conn, sql, fetchall=True)

    all_files = []
    if root.exists():
        all_files = [x for x in list(root.glob("**/*")) if not x.is_dir()]

    threads = []
    stats = {"views": 0}
    q = Queue()
    langs = [
        x.code
        for x in odoo.env["res.lang"].browse(odoo.env["res.lang"].search([]))
    ]

    def check_view():
        while not q.empty():
            count, view = q.get()
            try:
                for lang in langs:

                    def prog(c):
                        p = round(count / len(rows) * 100, 1)
                        click.secho(f"...threading progress {p}%", fg="yellow")

                    viewdb = odoo.env["ir.ui.view"].read(
                        [view[0]],
                        ["arch_db", "priority", "active"],
                        context={"lang": lang},
                    )[0]
                    xml = viewdb["arch_db"]
                    prio = viewdb["priority"]
                    active = "on" if viewdb["active"] else "off"
                    xmlid = _get_xml_id(config, "ir.ui.view", view[0])
                    model = view[3] or "no-model"
                    name = view[1]
                    id = view[0]

                    if xmlid:
                        filepath = (
                            root
                            / f"{model}.xmlid.{xmlid}.lang.{lang}.{prio}.{active}.xml"
                        )
                    else:
                        filepath = (
                            root
                            / "by_name"
                            / f"{model}.byname.{name}.{id}.lang.{lang}.xml"
                        )
                    filepath.parent.mkdir(exist_ok=True, parents=True)

                    path = filepath.parent / (filepath.stem + ".xml")

                    xml = xml.encode("utf8")
                    path.write_bytes(pretty_xml(xml))
                    if path in all_files:
                        all_files.remove(path)
                stats["views"] += 1
                if not stats["views"] % 800:
                    prog(stats["views"])
            except Exception as ex:
                click.secho(ex, fg="red")

    threads = []
    for count, view in enumerate(rows):
        q.put((count, view))

    for i in range(15):
        t = threading.Thread(target=check_view)
        t.daemon = True
        t.start()
        threads.append(t)
    [x.join() for x in threads]

    click.secho(f"Exported: {stats['views']} views.", fg="green")
    if all_files:
        for file in all_files:
            file.unlink()
            click.secho(
                f"View does not exist anymore: {file.relative_to(root)}"
            )


@src.command()
@click.option("-t", "--threads", default=10)
@click.argument("match", required=False)
@click.pass_context
@pass_config
def compare_views(config, ctx, threads, match):
    root = customs_dir() / "src"

    q = Queue()

    conn = config.get_odoo_conn()

    click.secho(
        'name="%(project_task_action_from_partner)d muss ersetzt werden',
        fg="red",
    )
    time.sleep(5)

    def compare_view(file_content, res_id, lang, info, the_model):
        view = _execute_sql(
            conn,
            f"select arch_db from ir_ui_view where id={res_id}",
            fetchone=True,
        )
        if not view:
            click.secho(f"VIEW vanished with id: {res_id} ({info})", fg="red")
        else:
            view = view[0]
            if current_version() < 16:
                view = {"en_US": view}
            for _lang, _arch in view.items():
                if _lang == lang:

                    def strippi(xml):
                        xml = xml.splitlines()
                        if "<?" in xml[0]:
                            xml = "\n".join(xml[1:])
                        else:
                            xml = "\n".join(xml)
                        for c in [" \t\n"]:
                            xml = xml.replace(c, "")
                        return xml

                    if strippi(file_content) != strippi(_arch):
                        click.secho(
                            f"Model: {the_model} -----------------------------------------------------------",
                            fg="yellow",
                        )
                        click.secho(f"VIEW {res_id} {info}", fg="green")
                        Path("/tmp/1").write_bytes(
                            pretty_xml(file_content.encode("utf8"))
                        )
                        Path("/tmp/2").write_bytes(
                            pretty_xml(_arch.encode("utf8"))
                        )
                        subprocess.run(
                            ["/bin/diff", "--color", "-w", "/tmp/1", "/tmp/2"]
                        )

    conn = config.get_odoo_conn()

    athreads = []

    def check_file():
        while not q.empty():
            file = q.get()
            if match and match not in file.stem:
                continue
            try:
                content = file.read_text()
                if ".xmlid." in file.stem:
                    try:
                        module, name, lang = file.stem.split(".xmlid.")[
                            1
                        ].split(".", 4)
                        model = file.stem.split(".xmlid.")[0]
                    except:
                        click.secho(
                            f"Invalid File Format: {file.relative_to(root)}",
                            fg="red",
                        )
                        return
                    xmlid = ".".join([module, name])

                    sql = (
                        f"select res_id "
                        f"from ir_model_data "
                        f"where model = 'ir.ui.view' "
                        f"and module='{module}' "
                        f"and name = '{name}'"
                    )
                    row = _execute_sql(conn, sql, fetchone=True)
                    if not row:
                        click.secho(f"XMLID vanished: {xmlid}", fg="red")
                    else:
                        arch = file.read_text()
                        compare_view(content, row[0], lang, xmlid, model)
                    del xmlid, module, name
                else:
                    content = file.read_text()
                    model = file.stem.split(".byname.")[0]
                    res_id = int(file.stem.split(".")[-2])
                    lang = file.stem.split(".")[-3]
                    compare_view(content, res_id, lang, "", model)
                    del res_id
            except Exception as ex:
                click.secho(ex, fg="red")

    for file in (customs_dir() / "src" / "views").glob("*.xml"):
        q.put(file)

    folder = customs_dir() / "src" / "views" / "by_name"
    if folder.exists():
        for file in folder.glob("*"):
            q.put(file)

    for _ in range(threads):
        t = threading.Thread(target=check_file)
        t.start()
        athreads.append(t)
    [t.join() for t in athreads]


@src.command()
@click.pass_context
@pass_config
def grab_models(config, ctx):
    root = customs_dir() / "src" / "models"

    sql = f"select id, model from ir_model"
    conn = config.get_odoo_conn()
    rows = _execute_sql(conn, sql, fetchall=True)
    q = Queue()

    for i, (id, model) in enumerate(rows):
        q.put(model)

    def do():
        while not q.empty():
            model = q.get()
            try:
                data = {
                    "model": model,
                    "fields": [],
                }
                fields = _execute_sql(
                    conn,
                    f"select name, ttype, compute, relation, translate, readonly from ir_model_fields where model = '{model}' order by model",
                    fetchall=True,
                )
                for field in sorted(fields, key=lambda x: x[0]):
                    data["fields"].append(
                        {
                            "name": field[0],
                            "type": field[1],
                            "compute": field[2],
                            "relation": field[3],
                            "translate": field[4],
                            "readonly": field[5],
                        }
                    )
                path = root / (model + ".json")
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_text(json.dumps(data, indent=4))

            except Exception as ex:
                click.secho("{e}", fg="red")

    threads = []
    for _ in range(10):
        t = threading.Thread(target=do)
        t.start()
        threads.append(t)
    [t.join() for t in threads]


@src.command()
@click.argument(
    "module",
    nargs=-1,
    shell_complete=_get_available_oca_modules,
    required=False,
)
@click.pass_context
@pass_config
def convert_odoo17_attrs(config, ctx, module):
    from .module_tools import Modules, Module
    from .lib_src_replace_attrs import odoo17attrs

    modules = Modules()
    all_modules = modules.get_all_modules_installed_by_manifest()
    for m in all_modules:
        if (module and m in module) or not module:
            m = Module.get_by_name(m)
            if m.is_customs or not module:
                odoo17attrs(customs_dir() / m.path)


@src.command()
@click.pass_context
@click.option("-c", "--customs", is_flag=True, help="Only customized modules.")
@pass_config
def srcstats(config, ctx, customs):
    pass

    res = []

    all_modules = _modules_overview(config)

    for m in sorted(all_modules, key=lambda x: x["name"]):
        if customs and not m["is_customs"]:
            continue
        m.pop("description")
        res.append(m)

    _output_clipboard_csv(res)


def _modules_overview(config):
    from .module_tools import Module, Modules

    modules = Modules()

    mods = modules.get_all_modules_installed_by_manifest()
    res = []
    for mod in mods:
        mod = Module.get_by_name(mod)
        manifest = mod.manifest_dict
        complexity = mod.calc_complexity()
        manifest = mod.manifest_dict

        combined_description = []
        for field in ["summary", "description"]:
            combined_description.append(manifest.get(field, ""))
        for readme in ["README.md", "README.rst", "README.txt"]:
            readmefile = mod.path / readme
            if readmefile.exists():
                combined_description.append(readmefile.read_text())
        description = "\n".join(filter(bool, combined_description))
        data = {
            "name": mod.name,
            "path": str(mod.path),
            "license": manifest.get("license") or "",
            "version": manifest.get("version"),
            "lines of code": complexity["loc"],
            "author": manifest.get("author", ""),
            "is_customs": mod.is_customs,
            "description": description,
        }
        res.append(data)
    return res


@src.command()
@click.argument("sha", required=True)
@click.pass_context
@pass_config
def analyze(config, ctx, sha):
    from .module_tools import Module

    result = {
        "manifests_changed": set(),
        "updated_modules": set(),
        "changed_xml_files": set(),
    }

    pychanges = subprocess.check_output(
        ["git", "log", "-p", f"{sha}..HEAD", "--", "*.py"],
        encoding="utf8",
        stderr=subprocess.DEVNULL,
    )
    filesoutput = subprocess.check_output(
        ["git", "log", "--name-only", "--pretty=format:", f"{sha}..HEAD"],
        encoding="utf8",
    ).splitlines()
    files = list(
        set(
            filter(
                bool,
                map(lambda x: x.strip(), filesoutput),
            )
        )
    )

    def _get_module_name(x):
        x = x.split("/")[-2].strip()
        if x == "...":
            x = ""
        try:
            m = Module.get_by_name(x)
        except Exception:
            return ""
        else:
            return str(m.name)

    result["changed_xml_files"] |= set(
        filter(
            bool,
            [_get_module_name(x) for x in files if ".xml" in x],
        )
    )
    result["manifests_changed"] |= set(
        filter(
            bool,
            [_get_module_name(x) for x in files if "__manifest__.py" in x],
        )
    )

    for module, line in splitdiff(pychanges):
        result["updated_modules"].add(str(module.name))

    result["updated_modules"] = list(sorted(result["updated_modules"]))
    result["changed_xml_files"] = list(sorted(result["changed_xml_files"]))
    result["manifests_changed"] = list(sorted(result["manifests_changed"]))
    print("----------------")
    print(json.dumps(result))


def splitdiff(diffoutput):
    module = None
    from .module_tools import Module

    remember = set()
    for line in diffoutput.splitlines():
        if line.startswith("diff --git"):
            filepath = line.split("b/")[0].split("a/")[1].strip()
            for part in Path(filepath).parts[:-1]:
                if part in remember:
                    continue
                try:
                    module = Module.get_by_name(part)
                except Exception:
                    remember.add(part)
                else:
                    break

        if module:
            yield module, line
