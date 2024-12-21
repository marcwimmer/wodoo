import traceback
import arrow
import re
import click
import os
from .tools import remove_webassets
from .tools import _execute_sql
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password
from .tools import __verify_password
from .tools import __replace_all_envs_in_str
from .tools import _update_setting
from .tools import abort


@cli.group(cls=AliasedGroup, name="dev-env")
@pass_config
def turn_into_dev(config):
    pass


@turn_into_dev.command()
@click.argument("password", required=False)
@click.option("-d", "--default", help="Set the default password", is_flag=True)
@click.pass_context
@pass_config
def set_password_all_users(config, ctx, password, default):
    from .odoo_config import current_version

    if default:
        password = config.DEFAULT_DEV_PASSWORD
    else:
        if not password:
            abort("Passwort required!")
    pwd = __hash_odoo_password(password)
    conn = config.get_odoo_conn().clone()
    sql = "select login, password from res_users"
    for user in _execute_sql(conn, sql, fetchall=True):
        if not __verify_password(password, user[1]):
            sql = f"update res_users set password='{pwd}' where login='{user[0]}'"
            _execute_sql(conn, sql)
    if current_version() in [11.0]:
        sql = f"update res_users set password_crypt=password"
        _execute_sql(conn, sql)

    # update a possible robot file also
    Commands.invoke(ctx, 'robot:make-var-file', userpassword=password)


@turn_into_dev.command()
@click.argument("password")
@pass_config
def hash_password(config, password):
    click.secho(__hash_odoo_password(password))


@turn_into_dev.command(name="turn-into-dev")
@pass_config
@click.pass_context
def turn_into_dev_(ctx, config):
    if not config.devmode and not config.force:
        raise Exception(
            (
                "When applying this sql scripts, "
                "the database is not usable anymore "
                "for production environments.\n"
                "Please set DEVMODE=1 to allow this"
            )
        )
    __turn_into_devdb(ctx, config, config.get_odoo_conn())


def __collect_other_turndb2dev_sql():
    from .odoo_config import customs_dir

    dir = customs_dir() / "devscripts"
    if not dir.exists():
        return ""
    sqls = []
    for file in dir.glob("turn-into-dev.sql"):
        sqls.append(file.read_text())
    return "\n\n".join(sqls)


def __turn_into_devdb(ctx, config, conn):
    from .odoo_config import current_version
    from .myconfigparser import MyConfigParser

    myconfig = MyConfigParser(config.files["settings"])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    sql_file = (
        config.dirs["images"]
        / "odoo"
        / "config"
        / str(current_version())
        / "turndb2dev.sql"
    )
    sql = sql_file.read_text()

    sql += __collect_other_turndb2dev_sql() or ""

    sql = __replace_all_envs_in_str(sql, env)

    critical = False
    for line in sql.split("\n"):
        if not line:
            continue
        if line.startswith("--set critical"):
            critical = True
            continue
        elif line.startswith("--set not-critical"):
            critical = False
            continue

        comment = re.findall(r"\/\*[^\*^\/]*\*\/", line)
        if comment:

            def ignore_line(comment):
                comment = comment[2:-2]
                if "if-table-exists" in comment:
                    table = comment.split("if-table-exists")[1].strip()
                    res = _execute_sql(
                        conn,
                        "select count(*) from information_schema.tables where table_schema='public' and table_name='{}'".format(
                            table
                        ),
                        fetchone=True,
                    )
                    return not res[0]
                if "if-column-exists" in comment:
                    table, column = (
                        comment.split("if-column-exists")[1].strip().split(".")
                    )
                    res = _execute_sql(
                        conn,
                        (
                            f"select count(*) "
                            f"from information_schema.columns "
                            f"where table_schema='public' and "
                            f"table_name='{table}' and column_name='{column}'"
                        ),
                        fetchone=True,
                    )
                    return not res[0]
                return False

            if any(list(ignore_line(comment) for comment in comment[0].split(";"))):
                continue
        try:
            print(line)
            _execute_sql(conn, line)
        except Exception:
            if critical:
                raise
            msg = traceback.format_exc()
            print("failed un-critical sql:", msg)

    remove_webassets(conn)
    _update_setting(
        conn=conn,
        key="web.base.url",
        value=f"http://localhost:{config.proxy_port}",
    )
    _update_setting(
        conn=conn,
        key="report.url",
        value=f"http://localhost:8069",
    )


@turn_into_dev.command()
@pass_config
def prolong(config):
    conn = config.get_odoo_conn()
    date = arrow.get().shift(months=6).strftime("%Y-%m-%d %H:%M:%S")
    _execute_sql(
        conn,
        (
            "UPDATE \n"
            "   ir_config_parameter "
            "SET "
            f"value = '{date}' "
            "WHERE "
            "key = 'database.expiration_date'"
        ),
    )


@turn_into_dev.command()
@click.option("--settings", required=True)
@pass_config
def remove_settings(config, settings):
    conn = config.get_odoo_conn()
    for setting in settings.split(","):
        _execute_sql(
            conn,
            """
            DELETE FROM
                ir_config_parameter
            WHERE key='{}'
        """.format(
                setting
            ),
        )


@turn_into_dev.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
@pass_config
def update_setting(config, key, value):
    conn = config.get_odoo_conn()
    _update_setting(conn, key, value)


Commands.register(set_password_all_users, "set-password-all-users")
