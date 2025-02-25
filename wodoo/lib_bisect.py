# not really a bisect, but acts ilike a bisect
import time
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

from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential


def _get_file():
    bisect_file = customs_dir() / ".bisect"
    if not bisect_file.exists():
        bisect_file.write_text(json.dumps({}))
    return json.loads(bisect_file.read_text())


def _save(content):
    bisect_file = customs_dir() / ".bisect"
    bisect_file.write_text(json.dumps(content, indent=4))


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
        "next": None,
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
    data['bad'].append(data['next'])
    data['turns'] += 1

    def remove_descendants_from_todo(data, module):
        from .module_tools import Modules, DBModules, Module

        base_module = Module.get_by_name(module)
        to_remove = [x.name for x in base_module.descendants]
        while to_remove:
            module = to_remove.pop()
            if module in data["todo"]:
                data['todo'].remove(module)

    remove_descendants_from_todo(data, data["next"])
    _get_next(data)
    _save(data)


@bisect.command()
@click.pass_context
@pass_config
def good(config, ctx):
    data = _get_file()
    data['good'].append(data['next'])
    data['turns'] += 1
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

    def _reset(module):
        @retry(
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        )
        def commando(*params, **kw):
            click.secho(f"Executing: odoo {' '.join(params)}", fg="green")
            Commands.invoke(ctx, *params, **kw)

        commando("kill")
        commando("kill", machines=['postgres'])
        commando("down", volumes=True)
        commando("reset-db")
        commando("wait_for_container_postgres", missing_ok=True)
        commando("update", module=module, no_restart=True, tests=False, no_dangling_check=True)
        commando("kill")
        commando("up", daemon=True)
        commando("wait_for_container_postgres", missing_ok=True)

    @retry(
        stop=stop_after_attempt(data['max_retries']),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def run_robot():
        try:
            result = Commands.invoke(
                ctx,
                "robot:run",
                file=robotest_file,
                no_sysexit=True,
                no_install_further_modules=True,
            )
        except:
            result = False
        return result

    if not data['next']:
        _get_next(data)
        _save(data)

    import pudb;pudb.set_trace()
    while data["next"]:
        module = data["next"]
        try:
            try:
                _reset(module)
            except Exception as ex:
                data = _get_file()
                data.setdefault("failed_installations", {})
                data["failed_installations"][module] = str(ex)
                _save(data)
            else:
                if robotest_file:
                    try:
                        result = run_robot()
                    except:
                        result = False
                    if result:
                        ctx.invoke(good)
                    else:
                        ctx.invoke(bad)
                        if data["stop_after_first_error"]:
                            break
                else:
                    click.secho(
                        "Please test now and then call odoo bisect good/bad", fg="yellow"
                    )
                    break
        finally:
            data = _get_file()
            _get_next(data)
            _save(data)
        ctx.invoke(bisect_status)

    click.secho("Finding error module done!", fg="green")
    ctx.invoke(bisect_status)


@bisect.command()
@click.pass_context
@pass_config
def bisect_status(config, ctx):
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
