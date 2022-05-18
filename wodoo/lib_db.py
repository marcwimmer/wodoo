import subprocess
from pathlib import Path
import sys
import re
import traceback
import os
import arrow
import click
from .tools import abort
from .tools import __replace_all_envs_in_str
from .tools import _wait_postgres
from .tools import _dropdb
from .tools import __dcrun, _remove_postgres_connections, _execute_sql
from .tools import exec_file_in_path
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password


@cli.group(cls=AliasedGroup)
@pass_config
def db(config):
    """
    Database related actions.
    """
    click.echo((
        f"database-name: {config.dbname}, "
        f"in ram: {config.run_postgres_in_ram}"
    ))

@db.command()
@pass_config
def db_health_check(config):
    conn = config.get_odoo_conn()
    click.secho((
        f"Connecting to {conn.host}:{conn.port}/{config.dbname}"
    ))
    try:
        _execute_sql(conn,
        "select * from pg_catalog.pg_tables;", fetchall=True)
    except Exception:  # pylint: disable=broad-except
        abort("Listing tables failed for connection to {conn.host}")
    else:
        click.secho((
            'Success'
        ), fg='green')

@db.command()
@click.argument('dbname', required=True)
@pass_config
def drop_db(config, dbname):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)
    conn = config.get_odoo_conn().clone(dbname='postgres')
    _remove_postgres_connections(
        conn, sql_afterwards=f"drop database {dbname};")
    click.echo("Database {} dropped.".format(dbname))

@db.command()
@pass_config
def pgactivity(config):
    from .tools import DBConnection
    conn = DBConnection(
        config.dbname,
        config.db_host,
        config.db_port,
        config.db_user,
        config.db_pwd
    )
    __dcrun([
        "pgtools", 'pg_activity',
        '-p', str(conn.port),
        '-U', conn.user,
        '-d', conn.dbname,
        '-h', conn.host,
        ], env={
            "PGPASSWORD": conn.pwd,
        }, interactive=True)

@db.command()
@click.argument('dbname', required=False)
@click.argument('params', nargs=-1)
@click.option('-h', '--host', required=False)
@click.option('-p', '--port', required=False)
@click.option('-u', '--user', required=False)
@click.option('-P', '--password', required=False)
@pass_config
def pgcli(config, dbname, params, host, port, user, password):
    from .tools import DBConnection

    dbname = dbname or config.dbname
    os.environ['ODOO_FRAMEWORK_KEEP_SQL_CONNECTION'] = '1'  # will be executed there so connection string will point to postgres

    if host:
        if any(not x for x in [port, user, password]):
            click.secho("If you provide a host, then provide please all connection informations.")
        conn = DBConnection(dbname, host, int(port), user, password)
    else:
        conn = config.get_odoo_conn().clone(dbname=dbname)
    return _pgcli(config, conn, params, use_docker_container=True)

@db.command()
@click.argument('dbname', required=False)
@click.argument('params', nargs=-1)
@click.option("--sql", required=False)
@click.option("-ni", "--non-interactive", is_flag=True)
@pass_config
def psql(config, dbname, params, sql, non_interactive):
    dbname = dbname or config.dbname
    os.environ['ODOO_FRAMEWORK_KEEP_SQL_CONNECTION'] = '1'  # will be executed there so connection string will point to postgres
    conn = config.get_odoo_conn().clone(dbname=dbname)
    return _psql(config, conn, params, sql=sql, interactive=not non_interactive)

def _psql(config, conn, params, bin='psql', sql=None, use_docker_container=None, interactive=True):
    dbname = conn.dbname
    if not dbname and len(params) == 1:
        if params[0] in ['postgres', dbname]:
            dbname = params[0]
            params = []
    params = " ".join(params)
    psql_args = ['-h', conn.host, '-p', str(conn.port), '-U', conn.user]
    if bin == 'psql':
        psql_args += ['-v', 'ON_ERROR_STOP=1']
    if sql:
        psql_args += ['-c', sql]
    if not interactive:
        psql_args += ['-q']
    try:
        cmd = psql_args
        cmd += [
            dbname,
        ]
        if use_docker_container or (config.use_docker and config.run_postgres):
            __dcrun(['pgtools', bin] + cmd, interactive=interactive, env={
                "PGPASSWORD": conn.pwd,
            })
        else:
            subprocess.call([
                exec_file_in_path(bin),
            ] + cmd, env={"PGPASSWORD": conn.pwd})
    finally:
        os.environ['PGPASSWORD'] = ""

def _pgcli(config, conn, params, use_docker_container=None):
    _psql(config, conn, params, bin='pgcli', use_docker_container=use_docker_container)

@db.command(name='reset-odoo-db')
@click.argument('dbname', required=False)
@click.option('--do-not-install-base', is_flag=True)
@pass_config
@click.pass_context
def reset_db(ctx, config, dbname, do_not_install_base):
    dbname = dbname or config.dbname
    if not dbname:
        raise Exception("dbname required")
    if config.run_postgres:
        Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
    _wait_postgres(config)
    conn = config.get_odoo_conn().clone(dbname=dbname)
    _dropdb(config, conn)
    conn = config.get_odoo_conn().clone(dbname='postgres')
    _execute_sql(
        conn,
        f"create database {dbname}",
        notransaction=True
    )

    # since odoo version 12 "-i base -d <name>" is required
    if not do_not_install_base:
        Commands.invoke(
            ctx,
            'update',
            module=['base'],
            since_git_sha=False,
            no_extra_addons_paths=True,
            no_restart=True,
            no_dangling_check=True,
            no_update_module_list=True,
            non_interactive=True,
        )

@db.command()
@pass_config
@click.pass_context
def anonymize(ctx, config):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)

    # Commands.invoke(
    #     ctx,
    #     'update',
    #     module=['anonymize'],
    #     no_restart=False,
    #     no_dangling_check=True,
    #     no_update_module_list=False,
    #     non_interactive=True,
    # )

    Commands.invoke(
        ctx,
        'odoo-shell',
        command=[
            'env["frameworktools.anonymizer"]._run()',
            'env.cr.commit()',
        ],
    )

@db.command()
@click.option("--no-update", is_flag=True)
@pass_config
@click.pass_context
def cleardb(ctx, config, no_update):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)

    if not no_update:
        Commands.invoke(
            ctx,
            'update',
            module=['cleardb'],
            no_restart=False,
            no_dangling_check=True,
            no_update_module_list=False,
            non_interactive=True,
        )

        # update of all modules then required, so that metainformation is
        # written to ir.model (the _cleardb flag on model)
        Commands.invoke(
            ctx,
            'update',
            module=[],
            no_restart=False,
            no_dangling_check=True,
            no_update_module_list=False,
            non_interactive=True,
        )

    Commands.invoke(
        ctx,
        'odoo-shell',
        command=[
            'env["frameworktools.cleardb"]._run()',
            'env.cr.commit()',
        ],
    )

@db.command(name='setname')
@click.argument("DBNAME", required=True)
@click.pass_context
def set_db_name(ctx, DBNAME):
    Commands.invoke(ctx, 'set_setting', key="DBNAME", value=DBNAME)

def __collect_other_turndb2dev_sql():
    from .odoo_config import customs_dir
    dir = customs_dir() / 'devscripts'
    if not dir.exists():
        return ""
    sqls = []
    for file in dir.glob("**/*.sql"):
        sqls.append(file.read_text())
    return "\n\n".join(sqls)

def __turn_into_devdb(config, conn):
    from .odoo_config import current_version
    from .myconfigparser import MyConfigParser
    myconfig = MyConfigParser(config.files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # encrypt password
    env['DEFAULT_DEV_PASSWORD'] = __hash_odoo_password(env['DEFAULT_DEV_PASSWORD'])

    sql_file = config.dirs['images'] / 'odoo' / 'config' / str(current_version()) / 'turndb2dev.sql'
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

        comment = re.findall(r'\/\*[^\*^\/]*\*\/', line)
        if comment:

            def ignore_line(comment):
                comment = comment[2:-2]
                if 'if-table-exists' in comment:
                    table = comment.split("if-table-exists")[1].strip()
                    res = _execute_sql(
                        conn,
                        (
                            "select count(*) "
                            "from information_schema.tables "
                            "where table_schema='public' and "
                            f"table_name='{table}'"
                        ),
                        fetchone=True
                    )
                    return not res[0]
                elif 'if-column-exists' in comment:
                    table, column = comment.split("if-column-exists")[1].strip().split(".")
                    res = _execute_sql(
                        conn,
                        (
                            "select count(*) "
                            "from information_schema.columns "
                            "where table_schema='public' and "
                            f"table_name='{table.strip()}' and "
                            "column_name='{column.strip()}' "
                        ),
                        fetchone=True
                    )
                    return not res[0]
                return False

            if any(list(
                    ignore_line(comment) for comment in comment[0].split(
                        ";"))):
                continue
        try:
            print(line)
            _execute_sql(conn, line)
        except Exception:
            if critical:
                raise
            msg = traceback.format_exc()
            print("failed un-critical sql:", msg)

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

@db.command(name='show-table-sizes')
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
    rows = _execute_sql(
        conn,
        sql,
        fetchall=True
    )
    from tabulate import tabulate
    if top:
        rows = rows[:top]
    click.echo(tabulate(rows, [
        "TABLE_NAME", "row_estimate", "total", 'INDEX', 'toast', 'TABLE']))

@db.command(help="Export as excel")
@click.argument("sql", required=True)
@click.option('-f', '--file')
@click.option('-b', '--base64', is_flag=True)
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
            f"{conn.dbname}_"
            f"{arrow.get().strftime('%Y-%m-%d%H-%M-%S')}.xlsx"
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
        if not irow % 1000:
            click.secho(f"Done {irow} rows...")

    workbook.close()

    click.secho(f"File created: {filepath}")
    if config.owner_uid:
        cmd = f'chown {config.owner_uid}:{config.owner_uid} "{filepath}"'
        os.system(cmd)

@db.command()
@click.option('--no-scram', is_flag=True)
@pass_config
def pghba_conf_wide_open(config, no_scram):
    conn = config.get_odoo_conn().clone(dbname='postgres')
    setting = _execute_sql(
        conn,
        "select setting from pg_settings where name like '%hba%';",
        fetchone=True)

    if not setting:
        click.secho("No pghba.conf location found.")
        return
    pghba_conf = setting[0]

    _execute_sql(
        conn, "drop table if exists hba;"
    )
    _execute_sql(
        conn, "create table hba ( lines text );"
    )

    _execute_sql(conn, f"copy hba from '{pghba_conf}';")
    _execute_sql(
        conn, (
            "delete from hba "
            "where lines like 'host%all%all%all%md5'"
    ))
    _execute_sql(
        conn, (
            "insert into hba (lines) "
            "values ('"
            f"host all all all md5"
            "');"
    ))
    if no_scram:
        _execute_sql(
            conn, (
                "update hba "
                " set lines = replace(lines, 'scram-sha-256', 'md5')"
        ))
    _execute_sql(conn, f"copy hba to '{pghba_conf}';")
    _execute_sql(conn, "select pg_reload_conf();")
    _execute_sql(conn, "drop table hba")
    _execute_sql(
        conn, "create table hba ( lines text );"
    )
    _execute_sql(conn, f"copy hba from '{pghba_conf}';")

    rows = _execute_sql(conn, (
        "select * from hba;"
    ), fetchall=True)
    for x in rows:
        if x[0].startswith("#"):
            continue
        print(x[0])


Commands.register(reset_db, 'reset-db')
