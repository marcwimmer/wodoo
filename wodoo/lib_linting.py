from pathlib import Path
from .tools import abort  # NOQA

import click

from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup


def _filter_comments(code):
    code = code.splitlines()
    code = [x for x in code if not x.strip().startswith("#")]
    return "\n".join(code)


@cli.group(cls=AliasedGroup)
@pass_config
def lint(config):
    pass


def _iterate_modules(config):
    from .module_tools import Modules, Module

    mods = Modules()
    modules = list(sorted(mods.get_all_modules_installed_by_manifest()))
    for module in modules:
        mod = Module.get_by_name(module)
        yield mod, Path(config.WORKING_DIR) / mod.path


@lint.command(name="all")
@pass_config
@click.pass_context
def lintall(ctx, config):
    ctx.invoke(breakpoint, no_raise_exception=False)


@lint.command()
@click.option("-E", "--no-raise-exception", is_flag=True)
@pass_config
def breakpoint(config, no_raise_exception):
    probs = []
    for mod, path in _iterate_modules(config):
        for pythonfile in path.glob("**/*.py"):
            code = _filter_comments(pythonfile.read_text())
            if "breakpoint()" in code:
                probs.append(
                    {"file": pythonfile.relative_to(config.WORKING_DIR)}
                )
    print("---")
    for prob in probs:
        click.secho(f"Breakpoint found in: {prob['file']}", fg="red")
    if probs:
        if not no_raise_exception:
            abort("Breakpoints found")


def odoolint(config):
    pass


# Commands.register(progress)
