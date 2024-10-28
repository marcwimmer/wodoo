import time
import subprocess
from pathlib import Path
import sys
import os
import arrow
import click
from .tools import _is_db_initialized
from .tools import abort
from .tools import _wait_postgres
from .tools import _dropdb
from .tools import __dcrun, _remove_postgres_connections, _execute_sql
from .tools import exec_file_in_path
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import _make_sure_module_is_installed
from .tools import print_prod_env
from .tools import _exists_db
from .odoo_config import get_conn_autoclose
from .tools import __dc


@cli.group(cls=AliasedGroup)
@pass_config
def db(config):
    """
    Database related actions.
    """
    click.echo(
        (f"database-name: {config.dbname}, " f"in ram: {config.run_postgres_in_ram}")
    )


@db.command()
@pass_config
def db_health_check(config):
    conn = config.get_odoo_conn()
    click.secho((f"Connecting to {conn.host}:{conn.port}/{config.dbname}"))
    try:
        _execute_sql(conn, "select * from pg_catalog.pg_tables;", fetchall=True)
    except Exception:  # pylint: disable=broad-except
        abort("Listing tables failed for connection to {conn.host}")
    else:
        click.secho(("Success"), fg="green")


@db.command()
@click.argument("dbname", required=True)
@pass_config
def drop_db(config, dbname):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg="red")
        sys.exit(-1)
    conn = config.get_odoo_conn().clone(dbname="postgres")
    _remove_postgres_connections(conn, sql_afterwards=f"drop database {dbname};")
    click.echo(f"Database {dbname} dropped.")


@db.command()
@pass_config
def pgactivity(config):
    from .tools import DBConnection

    conn = DBConnection(
        config.dbname, config.db_host, config.db_port, config.db_user, config.db_pwd
    )
    __dcrun(
        config,
        [
            "pgtools",
            "pg_activity",
            "-p",
            str(conn.port),
            "-U",
            conn.user,
            "-d",
            conn.dbname,
            "-h",
            conn.host,
        ],
        env={
            "PGPASSWORD": conn.pwd,
        },
        interactive=True,
    )


@db.command()
@click.argument("dbname", required=False)
@click.argument("params", nargs=-1)
@click.option("-h", "--host", required=False)
@click.option("-p", "--port", required=False)
@click.option("-u", "--user", required=False)
@click.option("-P", "--password", required=False)
@pass_config
def pgcli(config, dbname, params, host, port, user, password):
    from .tools import DBConnection

    print_prod_env(config)

    dbname = dbname or config.dbname

    if host:
        if any(not x for x in [port, user, password]):
            click.secho(
                "If you provide a host, then provide please all connection informations."
            )
        conn = DBConnection(dbname, host, int(port), user, password)
    else:
        conn = config.get_odoo_conn(inside_container=True).clone(dbname=dbname)
    return _pgcli(config, conn, params, use_docker_container=True)


@db.command()
@click.argument("dbname", required=False)
@click.argument("params", nargs=-1)
@click.option("--sql", required=False)
@click.option("-ni", "--non-interactive", is_flag=True)
@pass_config
def psql(config, dbname, params, sql, non_interactive):
    dbname = dbname or config.dbname
    conn = config.get_odoo_conn(inside_container=True).clone(dbname=dbname)
    return _psql(config, conn, params, sql=sql, interactive=not non_interactive)


def _psql(
    config,
    conn,
    params,
    bin="psql",
    sql=None,
    use_docker_container=None,
    interactive=True,
):
    dbname = conn.dbname
    if not dbname and len(params) == 1:
        if params[0] in ["postgres", dbname]:
            dbname = params[0]
            params = []
    params = " ".join(params)
    psql_args = ["-h", str(conn.host), "-U", conn.user]
    if conn.port:
        psql_args += ["-p", str(conn.port)]
    if bin == "psql":
        psql_args += ["-v", "ON_ERROR_STOP=1"]
    if sql:
        psql_args += ["-c", sql]
    if not interactive:
        psql_args += ["-q"]
    try:
        cmd = psql_args
        cmd += [
            dbname,
        ]

        if use_docker_container or (config.use_docker and config.run_postgres):
            __dcrun(
                config,
                ["pgtools", bin] + cmd,
                interactive=interactive,
                env={
                    "PGPASSWORD": conn.pwd,
                },
            )
        else:
            subprocess.call(
                [
                    exec_file_in_path(bin),
                ]
                + cmd,
                env={"PGPASSWORD": conn.pwd},
            )
    finally:
        os.environ["PGPASSWORD"] = ""


def _pgcli(config, conn, params, use_docker_container=None):
    _psql(config, conn, params, bin="pgcli", use_docker_container=use_docker_container)


def aggressive_drop_db(config, conn, dbname):
    for i in range(3):
        try:
            _dropdb(config, conn, dbname)
        except Exception as ex:
            click.secho(f"Error at dropping db at attempt {i + 1}: {ex}", fg="red")
            if config.run_postgres:
                click.secho(
                    f"Restarting postgres to remove any connections.", fg="yellow"
                )
                __dc(config, ["kill", "postgres"])
                __dc(config, ["up", "-d", "postgres"])
                _wait_postgres(config)
        if not _exists_db(conn, dbname):
            break
        click.secho(
            f"Database {dbname} was not dropped at first attempt. Retrying."
        )
        time.sleep(3)


@db.command(name="reset-odoo-db")
@click.argument("dbname", required=False)
@click.option("--do-not-install-base", is_flag=True)
@click.option("-W", "--no-overwrite", is_flag=True)
@pass_config
@click.pass_context
def reset_db(ctx, config, dbname, do_not_install_base, no_overwrite):
    import psycopg2
    collatec = True
    dbname = dbname or config.dbname
    if not dbname:
        raise Exception("dbname required")
    if config.run_postgres:
        Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
    _wait_postgres(config)

    if no_overwrite:
        try:
            with get_conn_autoclose() as cr:
                if _is_db_initialized(cr):
                    click.secho("Database already initialized. Skipping.", fg="yellow")
                    return
        except Exception:
            abort(
                "Could not talk to postgres server - cannot decide if db is initialized or not. Aborting"
            )

    conn = config.get_odoo_conn().clone(dbname="postgres")
    aggressive_drop_db(config, conn, dbname)

    cmd2 = ""
    if collatec:
        cmd2 = "LC_CTYPE 'C' LC_COLLATE 'C' ENCODING 'utf8' TEMPLATE template0"
    cmd = f"create database {dbname} {cmd2} "
    while True:
        try:
            _execute_sql(conn, cmd, notransaction=True)
            break
        except psycopg2.errors.DuplicateDatabase:
            aggressive_drop_db(config, conn, dbname)

    # since odoo version 12 "-i base -d <name>" is required
    if not do_not_install_base:
        Commands.invoke(
            ctx,
            "update",
            module=["base"],
            since_git_sha=False,
            no_extra_addons_paths=True,
            no_restart=True,
            no_dangling_check=True,
            no_update_module_list=True,
            non_interactive=True,
            no_outdated_modules=True,
        )


@db.command()
@pass_config
@click.pass_context
def anonymize(ctx, config):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg="red")
        sys.exit(-1)

    _make_sure_module_is_installed(
        ctx, config, "anonymize", "https://github.com/marcwimmer/odoo-anonymize.git"
    )

    Commands.invoke(
        ctx,
        "odoo-shell",
        command=[
            'env["frameworktools.anonymizer"]._run()',
            "env.cr.commit()",
        ],
    )


@db.command()
@click.option("-V", "--no-vacuum-full", is_flag=True)
@pass_config
@click.pass_context
def cleardb(ctx, config, no_vacuum_full):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg="red")
        sys.exit(-1)

    _make_sure_module_is_installed(
        ctx, config, "cleardb", "https://github.com/marcwimmer/odoo-cleardb.git"
    )
    str_no_vauum_full = "1" if no_vacuum_full else "0"

    Commands.invoke(
        ctx,
        "odoo-shell",
        command=[
            f'env["frameworktools.cleardb"]._run(no_vacuum_full={str_no_vauum_full})',
            "env.cr.commit()",
        ],
    )


@db.command(name="setname")
@click.argument("DBNAME", required=True)
@click.pass_context
def set_db_name(ctx, DBNAME):
    Commands.invoke(ctx, "set_setting", key="DBNAME", value=DBNAME)


@db.command()
@pass_config
@click.pass_context
def db_size(ctx, config):
    sql = f"select pg_database_size('{config.DBNAME}')"
    conn = config.get_odoo_conn()
    rows = _execute_sql(conn, sql, fetchall=True)
    if not rows:
        size = 0
    else:
        size = rows[0][0]
    click.secho("---")
    click.secho(size)


@db.command(name="show-table-sizes")
@pass_config
@click.pass_context
def show_table_sizes(ctx, config, top=20):
    sql = """
WITH RECURSIVE pg_inherit(inhrelid, inhparent) AS
    (select inhrelid, inhparent
    FROM pg_inherits
    UNION
    SELECT child.inhrelid, parent.inhparent
    FROM pg_inherit child, pg_inherits parent
    WHERE child.inhparent = parent.inhrelid),
pg_inherit_short AS (SELECT * FROM pg_inherit WHERE inhparent NOT IN (SELECT inhrelid FROM pg_inherit))
SELECT table_schema
    , TABLE_NAME
    , row_estimate
    , pg_size_pretty(total_bytes) AS total
    , pg_size_pretty(index_bytes) AS INDEX
    , pg_size_pretty(toast_bytes) AS toast
    , pg_size_pretty(table_bytes) AS TABLE
    FROM (
    SELECT *, total_bytes-index_bytes-COALESCE(toast_bytes,0) AS table_bytes
    FROM (
        SELECT c.oid
            , nspname AS table_schema
            , relname AS TABLE_NAME
            , SUM(c.reltuples) OVER (partition BY parent) AS row_estimate
            , SUM(pg_total_relation_size(c.oid)) OVER (partition BY parent) AS total_bytes
            , SUM(pg_indexes_size(c.oid)) OVER (partition BY parent) AS index_bytes
            , SUM(pg_total_relation_size(reltoastrelid)) OVER (partition BY parent) AS toast_bytes
            , parent
        FROM (
                SELECT pg_class.oid
                    , reltuples
                    , relname
                    , relnamespace
                    , pg_class.reltoastrelid
                    , COALESCE(inhparent, pg_class.oid) parent
                FROM pg_class
                    LEFT JOIN pg_inherit_short ON inhrelid = oid
                WHERE relkind IN ('r', 'p')
            ) c
            LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
    ) a
    WHERE oid = parent
) a
ORDER BY total_bytes DESC;
    """
    conn = config.get_odoo_conn()
    rows = _execute_sql(conn, sql, fetchall=True)
    from tabulate import tabulate

    if top:
        rows = rows[:top]
    click.echo(
        tabulate(
            rows, ["TABLE_NAME", "row_estimate", "total", "INDEX", "toast", "TABLE"]
        )
    )


@db.command(help="Export as excel")
@click.argument("sql", required=True)
@pass_config
def json(config, sql):
    import json as j

    conn = config.get_odoo_conn()
    columns, rows = _execute_sql(conn, sql, fetchall=True, return_columns=True)
    data2 = []
    for row in rows:
        record = dict(zip(columns, row))
        data2.append(record)
    data = j.dumps(data2, indent=4)
    print("------------------------\n")
    print(data)


@db.command(help="Export as excel")
@click.argument("sql", required=True)
@click.option("-f", "--file")
@click.option("-b", "--base64", is_flag=True)
@pass_config
def excel(config, sql, file, base64):
    import base64 as Base64

    if base64:
        sql = Base64.b64decode(sql)
    import xlsxwriter

    conn = config.get_odoo_conn()
    columns, rows = _execute_sql(conn, sql, fetchall=True, return_columns=True)
    click.secho(f"exporting {len(rows)} rows...")
    if file:
        filepath = Path(os.getcwd()) / file
    else:
        filepath = Path(os.getcwd()) / (
            f"{conn.dbname}_" f"{arrow.get().strftime('%Y-%m-%d%H-%M-%S')}.xlsx"
        )

    # Workbook() takes one, non-optional, argument
    # which is the filename that we want to create.
    workbook = xlsxwriter.Workbook(str(filepath))

    # The workbook object is then used to add new
    # worksheet via the add_worksheet() method.
    worksheet = workbook.add_worksheet()

    for icol, col in enumerate(columns):
        worksheet.write(0, icol, col)

    for irow, rec in enumerate(rows):
        for icol, col in enumerate(rec):
            worksheet.write(irow + 1, icol, col)
        if not irow % 1000 and irow:
            click.secho(f"Done {irow} rows...")

    workbook.close()

    click.secho(f"File created: {filepath}")
    if config.owner_uid:
        cmd = f'chown {config.owner_uid}:{config.owner_uid} "{filepath}"'
        os.system(cmd)


@db.command()
@click.option("--no-scram", is_flag=True)
@pass_config
def pghba_conf_wide_open(config, no_scram):
    conn = config.get_odoo_conn().clone(dbname="postgres")

    def adapt_pghba_conf():
        setting = _execute_sql(
            conn,
            "select setting from pg_settings where name like '%hba%';",
            fetchone=True,
        )

        if not setting:
            click.secho("No pghba.conf location found.")
            return
        pghba_conf = setting[0]

        _execute_sql(conn, "drop table if exists hba;")
        _execute_sql(conn, "create table hba ( lines text );")

        _execute_sql(conn, f"copy hba from '{pghba_conf}';")
        _execute_sql(
            conn, ("delete from hba " "where lines like 'host%all%all%all%md5'")
        )
        for method in ["trust", "scram", "md5"]:
            _execute_sql(
                conn,
                ("delete from hba " f"where lines like 'host%all%all%all%{method}'"),
            )

        def trustline():
            if config.devmode:
                trustline = "host all all all trust"
            else:
                if no_scram:
                    trustline = "host all all all md5"
                else:
                    trustline = "host all all all scram-sha-256"
            _execute_sql(conn, (f"insert into hba(lines) values('{trustline}');"))

        trustline()

        _execute_sql(conn, f"copy hba to '{pghba_conf}';")
        _execute_sql(conn, "select pg_reload_conf();")
        _execute_sql(conn, "drop table hba")
        _execute_sql(conn, "create table hba ( lines text );")
        _execute_sql(conn, f"copy hba from '{pghba_conf}';")

        rows = _execute_sql(conn, ("select * from hba;"), fetchall=True)
        for x in rows:
            if x[0].startswith("#"):
                continue
            print(x[0])

    def adapt_postgres_conf():
        setting = _execute_sql(
            conn,
            "select setting from pg_settings where name = 'config_file';",
            fetchone=True,
        )

        if not setting:
            click.secho("No postgresql.conf location found.")
            return
        conf = setting[0]

        _execute_sql(conn, "drop table if exists hba;")
        _execute_sql(conn, "create table hba ( lines text );")

        _execute_sql(conn, f"copy hba from '{conf}' with (delimiter E'~');")
        _execute_sql(
            conn, ("delete from hba " "where lines like '%password_encryption%'")
        )
        _execute_sql(conn, ("update hba set lines = replace(lines, '\t', ' ')"))
        if no_scram:
            _execute_sql(
                conn,
                (
                    "insert into hba (lines) "
                    "values ('"
                    f"password_encryption=md5"
                    "');"
                ),
            )
        _execute_sql(conn, f"copy hba to '{conf}';")
        _execute_sql(conn, "select pg_reload_conf();")
        _execute_sql(conn, "drop table hba")
        _execute_sql(conn, "create table hba ( lines text );")
        _execute_sql(conn, f"copy hba from '{conf}';")

        rows = _execute_sql(conn, ("select * from hba;"), fetchall=True)
        for x in rows:
            if x[0].startswith("#"):
                continue
            print(x[0])

    adapt_pghba_conf()
    adapt_postgres_conf()


Commands.register(reset_db, "reset-db")
Commands.register(pghba_conf_wide_open, "pghba_conf_wide_open")
