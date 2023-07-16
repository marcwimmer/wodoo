from pathlib import Path
import json
import subprocess
import inquirer
import sys
from datetime import datetime
import os
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
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
@click.argument("name", required=False)
@click.option("-M", "--module")
@click.option("-m", "--model")
@pass_config
def xmlids(config, name, module, model):
    conn = config.get_odoo_conn()
    where = " where 1 = 1"
    if model:
        where += f" AND model = '{model}'"
    if module:
        where += f" AND module = '{model}'"
    if name:
        where += (
            f" and (model ilike '%{name}%' or "
            f"name ilike '%{name}%' or "
            f"module ilike '%{name}%')"
        )
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
        click.secho(f"Turning {field} into create_date.", fg="green")
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
        click.echo(f"{row[0]}: {row[1]}")


@talk.command()
@pass_config
def modules_overview(config):
    from .module_tools import Modules, Module

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
            "description": description,
        }
        res.append(data)
    print("===")
    print(json.dumps(res, indent=4))


def _get_xml_id(conn, model, res_id):
    xmlid = _execute_sql(
        conn,
        sql=f"SELECT module||'.'||name FROM ir_model_data WHERE model = '{model}' AND res_id = {res_id}",
        params=(model, res_id),
        fetchone=True,
    )
    return xmlid and xmlid[0] or ""


@talk.command()
@click.argument("name", required=False, default="%")
@pass_config
def menus(config, name):
    conn = config.get_odoo_conn()
    ids = map(
        lambda x: x[0],
        _execute_sql(
            conn,
            sql=(
                f"SELECT id FROM ir_ui_menu WHERE name ILIKE '%{name}%' "
                f" UNION "
                f"SELECT res_id FROM ir_model_data WHERE model = 'ir.ui.menu' AND name ILIKE '%{name}%'"
            ),
            fetchall=True,
            return_columns=False,
        ),
    )

    def get_parents(parent_id):
        rows = _execute_sql(
            conn,
            sql=(
                "SELECT id, name, parent_id FROM ir_ui_menu " f"WHERE id = {parent_id}"
            ),
            fetchall=True,
            return_columns=False,
        )
        for row in rows:
            yield row
            if row[2]:
                yield from get_parents(row[2])

    ids = ",".join(map(str, ids))
    rows = _execute_sql(
        conn,
        sql=(f"SELECT id, name, parent_id FROM ir_ui_menu WHERE id in (0, {ids})"),
        fetchall=True,
        return_columns=True,
    )
    tablerows = []
    for row in rows[1]:
        xml_id = _get_xml_id(conn, "ir.ui.menu", row[0])
        row = list(row)
        path = "/".join(map(lambda x: x[1], reversed(list(get_parents(row[0])))))
        row.insert(0, xml_id)
        row.insert(0, path)
        row = row[:2]
        tablerows.append(row)
    cols = list(rows[0])[:2]
    cols.insert(0, "xmlid")
    cols.insert(0, "path")
    click.secho(tabulate(tablerows, cols, tablefmt="fancy_grid"), fg="yellow")


@talk.command()
@click.argument("name", required=False, default="%")
@pass_config
def groups(config, name):
    conn = config.get_odoo_conn()
    ids = map(
        lambda x: x[0],
        _execute_sql(
            conn,
            sql=(
                f"SELECT id FROM res_groups WHERE name ILIKE '%{name}%' "
                f" UNION "
                f"SELECT res_id FROM ir_model_data WHERE model = 'res.groups' AND name ILIKE '%{name}%'"
            ),
            fetchall=True,
            return_columns=False,
        ),
    )

    ids = ",".join(map(str, ids))
    rows = _execute_sql(
        conn,
        sql=(f"SELECT id, name FROM res_groups WHERE id in (0, {ids}) ORDER BY name"),
        fetchall=True,
        return_columns=True,
    )
    tablerows = []
    for row in rows[1]:
        xml_id = _get_xml_id(conn, "res.groups", row[0])
        row = list(row)
        row.insert(0, xml_id)
        row.pop(1)
        tablerows.append(row)
    cols = ["XML-ID", "Name"]
    click.secho(
        tabulate(sorted(tablerows, key=lambda x: x[0]), cols, tablefmt="fancy_grid"),
        fg="yellow",
    )


@talk.command()
@click.argument("login", required=False, default="%")
@pass_config
def users(config, login):
    conn = config.get_odoo_conn()
    rows = _execute_sql(
        conn,
        sql=(
            f"SELECT login, name FROM res_users INNER JOIN "
            f"res_partner p on p.id = res_users.partner_id "
            f"WHERE p.name ILIKE '%{login}%' or login ILIKE '%{login}%'"
        ),
        fetchall=True,
        return_columns=False,
    )

    cols = ["login", "name"]
    click.secho(
        tabulate(rows, cols, tablefmt="fancy_grid"),
        fg="yellow",
    )


Commands.register(progress)
