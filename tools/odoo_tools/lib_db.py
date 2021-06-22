import subprocess
import yaml
import arrow
import json
import pipes
import re
import traceback
import sys
import shutil
import hashlib
import os
import tempfile
import click
import inquirer
from datetime import datetime
from .tools import __replace_all_envs_in_str
from .tools import _wait_postgres
from .tools import _dropdb
from .tools import __assert_file_exists
from .tools import _exists_db
from .tools import __safe_filename
from .tools import remove_webassets
from .tools import __read_file
from .tools import __write_file
from .tools import _askcontinue
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import __dcrun, __dc, _remove_postgres_connections, _execute_sql, __dcexec
from .tools import get_volume_names
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
    click.echo("database-name: {}, in ram: {}".format(config.dbname, config.run_postgres_in_ram))

@db.command()
@click.argument('dbname', required=True)
@pass_config
def drop_db(config, dbname):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)
    conn = config.get_odoo_conn().clone(dbname='postgres')
    _remove_postgres_connections(conn, sql_afterwards="drop database {};".format(dbname))
    click.echo("Database {} dropped.".format(dbname))

@db.command()
@pass_config
def pgactivity(config):
    if config.run_postgres:
        __dcexec(["postgres", 'pg_activity'])

@db.command()
@click.argument('dbname', required=False)
@click.argument('params', nargs=-1)
@pass_config
def pgcli(config, dbname, params):
    dbname = dbname or config.dbname
    if config.use_docker:
        os.environ['DOCKER_MACHINE'] = "1"
    conn = config.get_odoo_conn().clone(dbname=dbname)
    return _pgcli(config, conn, params)

@db.command()
@click.argument('dbname', required=False)
@click.argument('params', nargs=-1)
@click.option("--sql", required=False)
@pass_config
def psql(config, dbname, params, sql):
    dbname = dbname or config.dbname
    if config.use_docker:
        os.environ['DOCKER_MACHINE'] = "1"
    conn = config.get_odoo_conn().clone(dbname=dbname)
    return _psql(config, conn, params, sql=sql)

def _psql(config, conn, params, bin='psql', sql=None):
    dbname = conn.dbname
    if not dbname and len(params) == 1:
        if params[0] in ['postgres', dbname]:
            dbname = params[0]
            params = []
    params = " ".join(params)
    psql_args = ['-h', conn.host, '-p', str(conn.port), '-U', conn.user]
    try:
        cmd = psql_args
        cmd += [
            dbname,
        ]

        if config.use_docker and config.run_postgres:
            __dcrun(['postgres', bin] + cmd, interactive=True, env={
                "PGPASSWORD": conn.pwd,
            })
        else:
            subprocess.call([
                exec_file_in_path('psql'),
            ] + cmd, env={"PGPASSWORD": conn.pwd})
    finally:
        os.environ['PGPASSWORD'] = ""

def _pgcli(config, conn, params):
    _psql(config, conn, params, bin='pgcli')

@db.command(name='reset-odoo-db')
@click.argument('dbname', required=False)
@click.option('--do-not-install-base', is_flag=True)
@pass_config
@click.pass_context
def reset_db(ctx, config, dbname, do_not_install_base):
    dbname = dbname or config.dbname
    if not dbname:
        raise Exception("dbname required")
    if config.run_docker:
        Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
    _wait_postgres(config)
    conn = config.get_odoo_conn().clone(dbname=dbname)
    _dropdb(config, conn)
    conn = config.get_odoo_conn().clone(dbname='postgres')
    _execute_sql(
        conn,
        "create database {}".format(
            dbname
        ),
        notransaction=True
    )

    # since odoo version 12 "-i base -d <name>" is required
    if not do_not_install_base:
        Commands.invoke(
            ctx,
            'update',
            module=['base'],
            since_git_sha=False,
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

    Commands.invoke(
        ctx,
        'update',
        module=['anonymize'],
        no_restart=False,
        no_dangling_check=True,
        no_update_module_list=False,
        non_interactive=True,
    )

    Commands.invoke(
        ctx,
        'odoo-shell',
        command=[
            'env["frameworktools.anonymizer"]._run()',
            'env.cr.commit()',
        ],
    )

@db.command()
@pass_config
@click.pass_context
def cleardb(ctx, config):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)

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
                        "select count(*) from information_schema.tables where table_schema='public' and table_name='{}'".format(table),
                        fetchone=True
                    )
                    return not res[0]
                elif 'if-column-exists' in comment:
                    table, column = comment.split("if-column-exists")[1].strip().split(".")
                    res = _execute_sql(
                        conn,
                        "select count(*) from information_schema.columns where table_schema='public' and table_name='{}' and column_name='{}' ".format(table.strip(), column.strip()),
                        fetchone=True
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
    click.echo(tabulate(rows, ["TABLE_NAME", "row_estimate", "total", 'INDEX', 'toast', 'TABLE']))


Commands.register(reset_db, 'reset-db')
