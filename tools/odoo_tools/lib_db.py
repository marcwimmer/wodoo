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
from .tools import _start_postgres_and_wait
from .tools import get_volume_names
from .tools import exec_file_in_path
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password
from . import PROJECT_NAME


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
    conn = config.get_odoo_conn()
    _remove_postgres_connections(conn)
    _execute_sql("drop database {};".format(dbname), dbname='template1', notransaction=True)
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
@pass_config
def psql(config, dbname, params):
    dbname = dbname or config.dbname
    if config.use_docker:
        os.environ['DOCKER_MACHINE'] = "1"
    conn = config.get_odoo_conn().clone(dbname=dbname)
    return _psql(config, conn, params)

def _psql(config, conn, params, bin='psql'):
    dbname = conn.dbname
    if not dbname and len(params) == 1:
        if params[0] in ['template1', dbname]:
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
@pass_config
@click.pass_context
def reset_db(ctx, config, dbname):
    dbname = dbname or config.dbname
    if not dbname:
        raise Exception("dbname required")
    _start_postgres_and_wait(config)
    conn = config.get_odoo_conn().clone(dbname=dbname)
    _dropdb(config, conn)
    conn = config.get_odoo_conn().clone(dbname='template1')
    _execute_sql(
        conn,
        "create database {}".format(
            dbname
        ),
        notransaction=True
    )

    # since odoo version 12 "-i base -d <name>" is required
    Commands.invoke(
        ctx,
        'update',
        module=['base'],
        no_restart=True,
        no_dangling_check=True,
        no_update_module_list=True,
        non_interactive=True,
    )

@db.command(name='anonymize')
@pass_config
@click.pass_context
def anonymize(ctx, config):
    if not (config.devmode or config.force):
        click.secho("Either DEVMODE or force required", fg='red')
        sys.exit(-1)

    # since odoo version 12 "-i base -d <name>" is required
    Commands.invoke(
        ctx,
        'update',
        module=['anonymize', 'cleardb'],
        no_restart=True,
        no_dangling_check=True,
        no_update_module_list=True,
        non_interactive=True,
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

def __turn_into_devdb(conn):
    from .odoo_config import current_version
    from . import MyConfigParser
    myconfig = MyConfigParser(files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # encrypt password
    env['DEFAULT_DEV_PASSWORD'] = __hash_odoo_password(env['DEFAULT_DEV_PASSWORD'])

    sql_file = dirs['images'] / 'odoo' / 'config' / str(current_version()) / 'turndb2dev.sql'
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


Commands.register(reset_db, 'reset-db')
