from pathlib import Path
from click.shell_completion import CompletionItem
import json
import yaml
import shutil
import subprocess
import inquirer
import sys
from datetime import datetime
import os
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .tools import _is_dirty
from .odoo_config import customs_dir
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import split_hub_url
from .tools import autocleanpaper
from .tools import copy_dir_contents, rsync
from .tools import abort
from .tools import __assure_gitignore
from .tools import _write_file
from .tools import bashfind

ADDONS_OCA = "addons_OCA"


@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass


@click.command()
@click.pass_context
@pass_config
def ensure_odoosh_repo(config, ctx):
    _ensure_odoosh_repo()


def _ensure_odoosh_repo():
    odoosh_path = Path(os.environ["ODOOSH_REPO"] or "../odoo.sh").resolve().absolute()
    if not odoosh_path.exists():
        subprocess.check_call(
            [
                "git",
                "clone",
                "https://github.com/Odoo-Ninjas/odoo.sh.git",
                odoosh_path,
            ]
        )
        subprocess.check_call(
            [
                "gimera",
                "apply",
            ],
            cwd=odoosh_path.absolute(),
        )
    return odoosh_path


def _build_gimera(path):
    gimera_file = path / "gimera.yml"
    if gimera_file.exists():
        content = yaml.safe_load(gimera_file.read_text())
    else:
        content = {
            "repos": [
                {
                    "branch": str(current_version()),
                    "url": "https://github.com/odoo/odoo",
                    "path": "odoo",
                    "type": "integrated",
                },
                {
                    "branch": str(current_version()),
                    "url": "git@github.com:odoo/enterprise",
                    "path": "enterprise",
                    "type": "integrated",
                },
                {
                    "branch": str(current_version()),
                    "url": "git@github.com:odoo/design-themes",
                    "path": "themes",
                    "type": "integrated",
                },
            ]
        }
        for repo in content["repos"]:
            __assure_gitignore(customs_dir() / ".gitignore", repo["path"] + "/")
    current_content = gimera_file.read_text() if gimera_file.exists() else ""
    new_content = yaml.dump(content, default_flow_style=False)

    content_changed = False
    if current_content != new_content:
        gimera_file.write_text(new_content)
        content_changed = True
    return content_changed


def _turn_into_odoosh(ctx, path):

    _ensure_odoosh_repo()
    content_changed = _build_gimera(path)

    repos = yaml.safe_load((path / "gimera.yml").read_text())
    _apply_gimera_if_required(ctx, path, repos, force_do=content_changed)
    _find_duplicate_modules()


def _find_duplicate_modules():
    from .module_tools import Modules

    modules = Modules()
    all_modules = modules.get_all_modules_installed_by_manifest()
    _identify_duplicate_modules(all_modules)


def _apply_gimera_if_required(ctx, path, content, force_do=False):
    def needs_apply():
        for repo in content["repos"]:
            repo_path = path / repo["path"]
            if not repo_path.exists():
                return True
        return False

    if force_do or needs_apply():
        subprocess.check_call(
            [
                "gimera",
                "apply",
            ],
            cwd=customs_dir(),
        )

        click.secho("Restarting reloading because gimera apply was done", fg="yellow")
        Commands.invoke(ctx, "reload", no_auto_repo=True)

        from .module_tools import Modules

        modules = Modules()
        all_modules = modules.get_all_modules_installed_by_manifest()


@src.command()
@click.pass_context
def apply_gimera_if_required(ctx):
    path = customs_dir()
    gimera_file = path / "gimera.yml"
    if not gimera_file.exists():
        if MANIFEST().get('auto_repo', False):
            _build_gimera(path)
        else:
            return
    repos = yaml.safe_load(gimera_file.read_text())
    _apply_gimera_if_required(ctx, path, repos)


@src.command()
@click.pass_context
@pass_config
def find_duplicate_modules(config, ctx):
    _find_duplicate_modules()


@src.command(name="init", help="Create a new odoo")
@click.argument("path", required=True)
@click.option("--odoosh", is_flag=True)
@click.pass_context
@pass_config
def init(config, ctx, path, odoosh):
    from .module_tools import make_customs

    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True)
    make_customs(ctx, path)

    odoosh and _turn_into_odoosh(ctx, Path(os.getcwd()))


@src.command(help="Makes odoo and enterprise code available from common code")
@click.pass_context
@pass_config
def make_odoo_sh_compatible(config, ctx):
    _turn_into_odoosh(ctx, customs_dir())


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
        "Updated ast - took {} seconds".format((datetime.now() - started).seconds)
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


@src.command(name="show-addons-paths")
def show_addons_paths():
    from .odoo_config import get_odoo_addons_paths

    paths = get_odoo_addons_paths(relative=True)
    for path in paths:
        click.echo(path)


@src.command(name="make-modules", help="Puts all modules in /modules.txt")
@pass_config
def make_modules(config):
    modules = ",".join(MANIFEST()["install"])
    (config.dirs["customs"] / "modules.txt").write_text(modules)
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
            abort("Please define ODOOSH_REPO env to point to checked out Ninja-Odoosh.")
        self.version = str(version)
        self.root = Path(os.environ["ODOOSH_REPO"])
        self.ocapath = self.root / "OCA"
        if not self.ocapath.exists():
            abort(f"Not found: {self.ocapath}")

    def iterate_all_modules(self, version, path=None):
        path = path or self.ocapath
        for path in bashfind(path=self.root, type="d", wholename=f"*/{version}/*"):
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
        all_modules = modules.get_all_modules_installed_by_manifest(current_modules)
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
        from .odoo_config import current_version, customs_dir

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


@src.command(help="Fetches OCA modules from odoo.sh ninja mentioned in MANIFEST")
@click.argument(
    "module", nargs=-1, shell_complete=_get_available_oca_modules, required=True
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
    from .module_tools import Modules, Module

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
    from .module_tools import Modules, Module

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


@src.command
@click.option("-f", "--fix-not-in-manifest", is_flag=True)
@pass_config
def show_installed_modules(config, fix_not_in_manifest):
    from .module_tools import DBModules, Module
    from .odoo_config import customs_dir

    path = customs_dir()
    collected = []
    not_in_manifest = []
    manifest = MANIFEST()
    setinstall = manifest.get("install", [])

    for module in sorted(DBModules.get_all_installed_modules()):
        try:
            mod = Module.get_by_name(module)
            click.secho(f"{module}: {mod.path}", fg="green")
            if not [x for x in setinstall if x == module]:
                not_in_manifest.append(module)
        except KeyError:
            collected.append(module)

    for module in not_in_manifest:
        if fix_not_in_manifest:
            setinstall += [module]
            click.secho(f"Added to manifest: {module}", fg="green")
        else:
            click.secho(f"Not in MANIFEST: {module}", fg="yellow")
    for module in collected:
        click.secho(f"Not in filesystem: {module}", fg="red")

    if fix_not_in_manifest:
        manifest["install"] = setinstall
        manifest.rewrite()


@src.command(name="pretty-print-manifest")
def pretty_print_manifest():
    from .odoo_config import MANIFEST

    MANIFEST().rewrite()
