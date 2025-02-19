# not really a bisect, but acts ilike a bisect
import json
import random
from .tools import _get_available_robottests
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .odoo_config import customs_dir
from .cli import cli, pass_config, Commands
import click
from .tools import abort
from .tools import _get_available_modules


def _get_file():
    bisect_file = customs_dir() / ".bisect"
    if not bisect_file.exists():
        bisect_file.write_text(json.dumps({}))
    return json.loads(bisect_file.read_text())


def _save(content):
    bisect_file = customs_dir() / ".bisect"
    bisect_file.write_text(json.dumps(content))


def _get_next(data):
    if not data["todo"]:
        data["next"] = ""
        return
    index = random.randint(0, len(data["todo"]) - 1)
    data["next"] = data["todo"].pop(index)
    data["current_try"] = 0


@cli.group(cls=AliasedGroup)
@pass_config
def bisect(config):
    pass


@bisect.command()
@click.argument(
    "robotest_file", required=False, shell_complete=_get_available_robottests
)
@click.option(
    "--dont-stop-after-first-error",
    is_flag=True,
)
@click.option("--retries", default=3, help="Max retries if robotest fails")
@click.pass_context
@pass_config
def start(config, ctx, robotest_file, dont_stop_after_first_error, retries):
    from .odoo_config import MANIFEST

    manifest = MANIFEST()
    all_modules = sorted(manifest.get("install", []))
    data = {
        "todo": all_modules,
        "next": all_modules[random.randint(0, len(all_modules) - 1)],
        "good": [],
        "bad": [],
        "turns": 0,
        "done": [],
        "robotest_file": robotest_file,
        "stop_after_first_error": not dont_stop_after_first_error,
        "max_retries": retries,
        "current_try": 0,
    }
    _save(data)
    if not robotest_file:
        click.secho(
            """
            No robotest file set. Please call:

            > odoo bisect run 
            
            and then 

            > odoo bisect good/bad
            """,
            fg="yellow",
        )


@bisect.command()
@click.pass_context
@pass_config
def bad(config, ctx):
    data = _get_file()

    def remove_descendants_from_todo(data, module):
        from .module_tools import Modules, DBModules, Module

        base_module = Module.get_by_name(module)
        to_remove = [x.name for x in base_module.descendants]
        while to_remove:
            module = to_remove.pop()
            if module in data["todo"]:
                data.remove(module)

    remove_descendants_from_todo(data, data["next"])
    _get_next(data)
    _save(data)


@bisect.command()
@click.pass_context
@pass_config
def good(config, ctx):
    data = _get_file()
    _get_next(data)
    _save(data)


@bisect.command()
@click.argument("module")
@click.pass_context
@pass_config
def testdep(config, ctx, module):

    data = _get_file()
    removed = _remove_from_todo_because_module_failed(module)
    click.secho(removed)


@bisect.command()
@click.pass_context
@pass_config
def run(config, ctx):
    data = _get_file()
    if not config.devmode and not config.force:
        abort("Requires devmode")
    if not config.force:
        abort("Please use the force mode!")
    robotest_file = data["robotest_file"]

    def _reset():
        Commands.invoke(ctx, "kill", machines=["postgres"])
        Commands.invoke(ctx, "reset-db")
        Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)
        Commands.invoke(
            ctx, "update", data["next"], tests=False, no_dangling_check=True
        )

    _reset()

    def _uninstall(module):
        try:
            Commands.invoke(
                ctx, "uninstall", module, tests=False, no_dangling_check=True
            )
        except:
            _reset()

    while data["next"]:
        import pudb

        pudb.set_trace()
        module = data["next"]

        if robotest_file:
            result = Commands.invoke(
                ctx, "robot:run", file=robotest_file, no_sysexit=True
            )
            if result:
                ctx.invoke(good)
                _uninstall(module)
            else:
                data.setdefault("current_try", 0)
                if data["current_try", 0] < data["max_retries"]:
                    data["current_try"] += 1
                    _save(data)
                else:
                    ctx.invoke(bad)
                    if data["stop_after_first_error"]:
                        break
                    else:
                        _uninstall(module)
        else:
            click.secho(
                "Please test now and then call odoo bisect good/bad", fg="yellow"
            )
            break
        data = _get_file()
        ctx.invoke(status)

    click.secho("Finding error module done!", fg="green")
    ctx.invoke(status)


@bisect.command()
@click.pass_context
@pass_config
def status(config, ctx):
    data = _get_file()
    if not data:
        abort("No bisect started.")
    click.secho(f"Turns: {data['turns']}", fg="green")
    click.secho(f"Good: {data['good']}", fg="green")
    click.secho(f"Bad: {data['bad']}", fg="green")
    click.secho(f"Next: {data['next']}", fg="green")


@bisect.command()
@click.argument(
    "module", nargs=-1, required=False, shell_complete=_get_available_modules
)
@click.pass_context
@pass_config
def redo(config, ctx, module):
    data = _get_file()
    modules2 = []
    for x in module:
        modules2 += x.split(",")

    data["todo"] += modules2
    _save(data)
    modules2 = ",".join(modules2)
    click.secho(f"Added: {modules2}", fg="green")
