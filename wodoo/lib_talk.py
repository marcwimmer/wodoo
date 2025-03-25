import json
import arrow
import time

import click
from tabulate import tabulate

from .cli import Commands, cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import _execute_sql
from .tools import _get_setting


def _stringify_translated_dict(v):
    if isinstance(v, dict):
        res = []
        for k, d in v.items():
            if k != "en_US":
                continue
            res.append(d)
            # res.append(f"{k}: {d}")
        return ", ".join(res)
    else:
        return v


@cli.group(cls=AliasedGroup)
@pass_config
def talk(config):
    pass


@talk.command()
@click.argument("name", required=False, nargs=-1)
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
    for name in name:
        where += (
            f" and ( (model ilike '%{name}%' or "
            f"name ilike '%{name}%' or "
            f"module ilike '%{name}%'))"
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
@pass_config
@click.pass_context
def get_config_parameter(ctx, config, name):
    conn = config.get_odoo_conn()
    click.secho(_get_setting(conn, name))


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
                ctx,
                "update",
                module=["web_environment_ribbon"],
                no_dangling_check=True,
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
    help=(
        "If menu items are missing, then recomputing the parent store"
        "can help"
    )
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
    from .lib_src import _modules_overview

    res = _modules_overview(config)
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
                f"SELECT id FROM ir_ui_menu WHERE name::text ILIKE '%{name}%' "
                f" UNION "
                f"SELECT res_id FROM ir_model_data WHERE model = 'ir.ui.menu' AND name::text ILIKE '%{name}%'"
            ),
            fetchall=True,
            return_columns=False,
        ),
    )

    def get_parents(parent_id):
        rows = _execute_sql(
            conn,
            sql=(
                "SELECT id, name, parent_id FROM ir_ui_menu "
                f"WHERE id = {parent_id}"
            ),
            fetchall=True,
            return_columns=False,
        )
        for row in rows:
            yield row
            if row[2]:
                yield from get_parents(row[2])

    ids = ",".join(map(str, [0] + list(ids)))
    rows = _execute_sql(
        conn,
        sql=(
            f"SELECT id, name, parent_id FROM ir_ui_menu WHERE id in ({ids})"
        ),
        fetchall=True,
        return_columns=True,
    )
    tablerows = []
    for row in rows[1]:
        xml_id = _get_xml_id(conn, "ir.ui.menu", row[0])
        row = list(row)
        path = "/".join(
            map(
                lambda x: _stringify_translated_dict(x[1]),
                reversed(list(get_parents(row[0]))),
            )
        )
        row.insert(0, xml_id)
        row.insert(0, path)
        row = row[:2]
        tablerows.append(row)
    cols = list(rows[0])[:2]
    cols.insert(0, "xmlid")
    cols.insert(0, "path")
    tablerows = list(sorted(tablerows, key=lambda x: x[0]))
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
                f"SELECT id FROM res_groups WHERE name::text ILIKE '%{name}%' "
                f" UNION "
                f"SELECT res_id FROM ir_model_data WHERE model = 'res.groups' AND name::text ILIKE '%{name}%'"
            ),
            fetchall=True,
            return_columns=False,
        ),
    )

    ids = ",".join(map(str, [0] + list(ids)))
    rows = _execute_sql(
        conn,
        sql=(
            f"SELECT id, name FROM res_groups WHERE id in ({ids}) ORDER BY name"
        ),
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
        tabulate(
            sorted(tablerows, key=lambda x: x[0]), cols, tablefmt="fancy_grid"
        ),
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
            f"SELECT res_users.id as user_id, login, name FROM res_users INNER JOIN "
            f"res_partner p on p.id = res_users.partner_id "
            f"WHERE p.name ILIKE '%{login}%' or login ILIKE '%{login}%'"
        ),
        fetchall=True,
        return_columns=False,
    )

    cols = ["login", "name", "user_id"]
    click.secho(
        tabulate(rows, cols, tablefmt="fancy_grid"),
        fg="yellow",
    )


@talk.command()
@click.argument("model", required=False, default="%")
@click.argument("field", required=False, default="%")
@pass_config
def fields(config, model, field):
    conn = config.get_odoo_conn()
    sql = (
        "SELECT f.name, f.ttype "
        "FROM ir_model_fields f INNER JOIN "
        "ir_model m ON "
        "f.model_id = m.id "
        "WHERE 1=1 "
    )
    if model:
        sql += f" AND m.model ilike '%{model}%' "
    if field:
        sql += f" AND f.name ilike '%{field}%' "

    rows = _execute_sql(
        conn,
        sql=sql,
        fetchall=True,
        return_columns=False,
    )

    cols = ["name", "ttype"]
    click.secho(
        tabulate(rows, cols, tablefmt="fancy_grid"),
        fg="yellow",
    )


@talk.command()
@click.option("-i", "--interval", default=5, type=int)
@pass_config
def queuejobs(config, interval):
    conn = config.get_odoo_conn()
    last_data, last_time = None, None
    averages = {}
    while True:
        rows = _execute_sql(
            conn,
            sql=(
                "SELECT count(*) as count, state "
                "FROM queue_job "
                "GROUP BY state "
                "UNION "
                "SELECT count(*), 'total' FROM queue_job"
            ),
            fetchall=True,
            return_columns=True,
        )
        rows = list(rows)
        rows[1] = sorted(
            rows[1], key=lambda x: x[1] == "total" and "zzzzzzzz" or x[1]
        )
        data = {x[1]: x[0] for x in rows[1]}

        click.secho(
            tabulate(rows[1], rows[0], tablefmt="fancy_grid"), fg="yellow"
        )
        if last_data:
            click.secho("Changes: ")
            now = arrow.get()
            avg_rows = []
            for state, v in data.items():
                diff = data.get(state, 0) - last_data.get(state, 0)
                seconds = round((now - last_time).total_seconds())
                if seconds:
                    diff_per_second = round(abs(diff / seconds), 1)
                else:
                    diff_per_second = 0
                averages.setdefault(state, [])
                averages[state].append(diff_per_second)
                avg_diff_per_second = round(
                    sum(averages[state]) / len(averages[state]), 1
                )
            click.secho(
                tabulate(
                    avg_rows,
                    ["state", "items", "items per second"],
                    tablefmt="fancy_grid",
                ),
                fg="blue",
            )
            # click.secho(f"{state}: {diff} with {avg_diff_per_second}/s")

        time.sleep(interval)
        last_data = data
        last_time = arrow.get()


def _get_xmlid(conn, id, model):
    where = f"model = 'ir.ui.view' and res_id={id}"
    sql = (
        "SELECT module||'.'|| name as xmlid, model, res_id from ir_model_data "
        f"where {where} "
    )
    rows = _execute_sql(
        conn,
        sql=sql,
        fetchall=True,
        return_columns=False,
    )
    if rows:
        return rows[0][0]
    return None


@talk.command()
@click.option("-M", "--module")
@click.argument("model", required=True)
@click.argument("name", required=False)
@click.option("-t", "--type")
@pass_config
def views(config, name, module, model, type):
    conn = config.get_odoo_conn()

    where = f"model = '{model}'"
    where += "AND inherit_id is null"
    rows = _execute_sql(
        conn,
        sql=f"select id, name, type from ir_ui_view where {where}",
        fetchall=True,
        return_columns=True,
    )

    rows = list(rows)
    if type:
        rows[1] = list(filter(lambda x: x[2] == type, rows[1]))

    rows2 = []
    for row in rows[1]:
        row = list(row)
        row.append(_get_xmlid(conn, row[0], "ir.ui.view"))
        rows2.append(row)
    rows[0] = list(rows[0])
    rows[0].append("xmlid")
    click.secho(tabulate(rows2, rows[0], tablefmt="fancy_grid"), fg="yellow")


@talk.command()
@pass_config
@click.pass_context
def set_remote_keys(ctx, config):
    Commands.invoke(
        ctx,
        "odoo-shell",
        command=[
            'env["res.users"].set_remote_keys();',
            "env.cr.commit()",
        ],
    )


Commands.register(progress)
