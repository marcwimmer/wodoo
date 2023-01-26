from pathlib import Path
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
from .tools import _execute_sql
from tabulate import tabulate
from .cli import cli, pass_config, Commands


@cli.group(cls=AliasedGroup)
@pass_config
def talk(config): 
    pass

@talk.command()
@click.option("-M", "--module")
@click.option("-m", "--model")
@pass_config
def xmlids(config, module, model):
    conn = config.get_odoo_conn()
    where = " where 1 = 1"
    if model:
        where += f" AND model = '{model}'"
    if module:
        where += f" AND module = '{model}'"
    rows = _execute_sql(
        conn,
        sql=(
            "SELECT module||'.'|| name as xmlid, model, res_id from ir_model_data "
            f"{where} "
            "order by module, name, model "
        ),
        fetchall=True,
        return_columns=True,
    )
    click.secho(tabulate(rows[1], rows[0], tablefmt="fancy_grid"), fg="yellow")

@talk.command()
@click.argument("field", nargs=-1)
@pass_config
def deactivate_field_in_views(config, field):
    conn = config.get_odoo_conn()
    for field in field:
        click.secho(f"Turning {field} into create_date.", fg='green')
        _execute_sql(
            conn,
            sql=(
                "UPDATE ir_ui_view set arch_db = "
                f"replace(arch_db, '{field}', 'create_date')"
            ),
            fetchall=False,
            return_columns=False,
        )

@talk.command()
@click.argument("name", required=True)
@click.option("-Q", "--quick", is_flag=True)
@pass_config
@click.pass_context
def set_ribbon(ctx, config, name, quick):
    if not quick:
        SQL = """
            Select state from ir_module_module where name = 'web_environment_ribbon';
        """
        res = _execute_sql(config.get_odoo_conn(), SQL, fetchone=True)
        if not (res and res[0] == "installed"):
            Commands.invoke(
                ctx, "update", module=["web_environment_ribbon"], no_dangling_check=True
            )

    _execute_sql(
        config.get_odoo_conn(),
        """
        UPDATE
            ir_config_parameter
        SET
            value = %s
        WHERE
            key = 'ribbon.name';
    """,
        params=(name,),
    )


@talk.command(
    help=(
        "As the name says: if db was transferred, web-icons are restored"
        " on missing assets"
    )
)
@pass_config
@click.pass_context
def restore_web_icons(ctx, config):
    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell

    click.secho("Restoring web icons...", fg="blue")
    lib_shell(
        config,
        (
            "for x in self.env['ir.ui.menu'].search([]):\n"
            "   if not x.web_icon: continue\n"
            "   x.web_icon_data = x._compute_web_icon_data(x.web_icon)\n"
            "   env.cr.commit()\n"
        ),
    )
    click.secho("Restored web icons.", fg="green")


@talk.command(
    help=("If menu items are missing, then recomputing the parent store" "can help")
)
@pass_config
@click.pass_context
def recompute_parent_store(ctx, config):
    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell

    click.secho("Recomputing parent store...", fg="blue")
    lib_shell(
        config,
        (
            "for model in self.env['ir.model'].search([]):\n"
            "   try:\n"
            "       obj = self.env[model.model]\n"
            "   except KeyError: pass\n"
            "   else:\n"
            "       obj._parent_store_compute()\n"
            "       env.cr.commit()\n"
        ),
    )
    click.secho("Recompute parent store done.", fg="green")


@talk.command()
@pass_config
def progress(config):
    """
    Displays installation progress
    """
    for row in _execute_sql(
        config.get_odoo_conn(),
        "select state, count(*) from ir_module_module group by state;",
        fetchall=True,
    ):
        click.echo("{}: {}".format(row[0], row[1]))


Commands.register(progress)