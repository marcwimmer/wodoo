from pathlib import Path
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
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import split_hub_url
from .tools import autocleanpaper
from .tools import copy_dir_contents, rsync


@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass


@src.command(help="Create a new odoo")
@click.argument("path", required=True)
@pass_config
def init(config, path):
    from .module_tools import make_customs

    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True)
    make_customs(path)


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


@src.command()
@click.argument("branch", required=True)
@pass_config
def pack_to_branch(config, branch):
    from .module_tools import Modules, DBModules, Module

    def _collect_external_deps(modules):
        python = set()
        for module in modules:
            d = module.manifest_dict
            [ python.add(x) for x in d.get("external_dependencies", {}).get("python", [])]
        return python

    with autocleanpaper() as folder:
        folder.mkdir(exist_ok=True, parents=True)
        custdir = customs_dir()
        exclude = [
            x.name
            for x in custdir.glob("*")
            if x.is_dir() and x.name not in [".git"]
        ]
        rsync(
            custdir,
            folder,
            exclude=exclude,
        )
        try:
            subprocess.check_call(["git", "checkout", "-f", branch], cwd=folder)
        except:
            subprocess.check_call(["git", "checkout", "-b", branch], cwd=folder)
        subprocess.check_call(["git", "pull"], cwd=folder)
        subprocess.check_call(["git", "clean", "-xdff"], cwd=folder)

        # remove everything in this branch
        for d in folder.glob("*"):
            if d.is_dir() and d.name != '.git':
                shutil.rmtree(d)

        mods = Modules()
        modules = list(sorted(mods.get_all_modules_installed_by_manifest()))
        modules = [Module.get_by_name(x) for x in modules]
        # filter out odoo
        modules = [
            x
            for x in modules
            if x.path.parts[0] not in ["odoo", "enterprise", "odoo_enterprise"]
        ]
        for mod in modules:
            dest = folder / mod.path.name
            dest.mkdir(parents=True)
            rsync(mod.path, dest)

        comment = subprocess.check_output(["git", "log", "-n1"], encoding="utf8")

        # remove unneeded files
        for subfolder in folder.glob("*"):
            if subfolder.name == ".git":
                continue
            if not subfolder.is_dir():
                if not str(subfolder).startswith("."):
                    subfolder.unlink()
                continue

        python = _collect_external_deps(modules)
        if python:
            (folder / 'requirements.txt').write_text('\n'.join(sorted(python)))

        subprocess.check_call(["git", "add", "."], cwd=folder)
        subprocess.check_call(
            ["git", "commit", "-am", comment.replace("\n", " ")], cwd=folder
        )
        subprocess.check_call(
            ["git", "push", "--set-upstream", "origin", branch], cwd=folder
        )
