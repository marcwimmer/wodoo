import json
import pipes
import re
import subprocess
import traceback
import sys
import shutil
import hashlib
import os
import tempfile
import click
from tools import _dropdb
from tools import DBConnection
from tools import __assert_file_exists
from tools import __exists_db
from tools import __system
from tools import __set_db_ownership
from tools import __safe_filename
from tools import remove_webassets
from tools import __find_files
from tools import __read_file
from tools import __write_file
from tools import _askcontinue
from tools import __append_line
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from tools import __dcrun, __dc, __remove_postgres_connections, __execute_sql, __dcexec
from tools import __start_postgres_and_wait
from . import cli, pass_config, dirs, files, Commands
from lib_clickhelpers import AliasedGroup
from lib_remoteaccess import get_config, get_areas

@cli.group(cls=AliasedGroup)
@pass_config
def db(config):
    """
    Database related actions.
    """
    click.echo("database-name: {}, in ram: {}".format(config.dbname, config.run_postgres_in_ram))
    pass

@cli.group(cls=AliasedGroup)
@pass_config
def snapshot(config):
    pass

def __assert_btrfs(config):
    if not config.run_btrfs:
        click.echo("Please enable RUN_BTRFS=1 and make sure, that volumes are using the anybox/buttervolume docker plugin")
        sys.exit(-1)

@snapshot.command(name="list")
@pass_config
def do_list(config):
    __assert_btrfs(config)
    os.system('buttervolume snapshots')


    raise Exception('stop')

    args = ['postgres_snapshot']
    if todo == 'save':
        args += ['/usr/bin/rsync', '-ar', '--info=progress2', '/opt/data/', '/opt/snapshot/']
        __dcrun(args, interactive=True)
        __dc(['stop', '-t 1'] + ['postgres'])
        args += ['/usr/bin/rsync', '-ar', '--info=progress2', '/opt/data/', '/opt/snapshot/', '--delete']
        __dcrun(args)
        __dc(['up', '-d'] + ['postgres'])
    elif todo == 'restore':
        __dc(['kill'] + ['postgres'])
        args += ['/usr/bin/rsync', '-arP', '--info=progress2', '/opt/snapshot/', '/opt/data/', '--delete']
        __dcrun(args)
        __dc(['up', '-d'] + ['postgres'])

@db.command()
@click.argument('dbname', required=True)
@pass_config
def drop_db(config, dbname):

    if not (config.devmode or config.force):
        click.echo("Either DEVMODE or force required")
        sys.exit(-1)
    __remove_postgres_connections(dbname)
    __execute_sql("drop database {};".format(dbname), dbname='template1', notransaction=True)
    click.echo("Database {} dropped.".format(dbname))

@db.command()
@pass_config
def pgactivity(config):
    if config.run_postgres:
        __dcexec(["postgres", 'pg_activity'])


@db.command()
@pass_config
def turn_into_dev(config):
    if not config.devmode:
        raise Exception("""When applying this sql scripts, the database is not usable anymore for production environments.
Please set DEVMODE=1 to allow this""")
    __turn_into_devdb(config.get_odoo_conn())

@db.command()
@click.argument('dbname', required=False)
@click.argument('params', nargs=-1)
@pass_config
def psql(config, dbname, params):
    dbname = dbname or config.dbname
    conn = config.get_odoo_conn().clone(dbname=dbname)
    return _psql(conn, params)

def _psql(conn, params):
    from . import stdinput
    dbname = conn.dbname
    if not dbname and len(params) == 1:
        if params[0] in ['template1', dbname]:
            dbname = params[0]
            params = []
    params = " ".join(params)
    psql_args = ['-h', conn.host, '-p', str(conn.port), '-U', conn.user]
    try:
        os.environ['PGPASSWORD'] = conn.pwd
        if stdinput:
            proc = subprocess.Popen(
                ['psql'] + psql_args + [dbname],
                bufsize=1024,
                stdin=subprocess.PIPE,
            )
            proc.stdin.write(input)
            proc.stdin.close()
            proc.wait()
        else:
            cmd = "psql {} {} ".format(" ".join(pipes.quote(s) for s in psql_args), dbname) + params
            os.system(cmd)
    finally:
        os.environ['PGPASSWORD'] = ""

@db.command(name='reset-odoo-db')
@click.argument('dbname', required=False)
@pass_config
def reset_db(config, dbname):
    dbname = dbname or config.dbname
    if not dbname:
        raise Exception("dbname required")
    __start_postgres_and_wait(config)
    conn = config.get_odoo_conn().clone(dbname=dbname)
    _dropdb(config, conn)

@db.command(name='setname')
@click.argument("DBNAME", required=True)
@click.pass_context
def set_db_name(ctx, DBNAME):
    Commands.invoke(ctx, 'set_setting', key="DBNAME", value=DBNAME)

@db.command(name='set-ownership')
@pass_config
def set_db_ownership(config):
    __set_db_ownership(config)


def __turn_into_devdb(conn):
    SQLFILE = files['machines/postgres/turndb2dev.sql']
    sql = __read_file(SQLFILE)

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
            for comment in comment[0].split(";"):
                comment = comment[2:-2]
                if 'if-table-exists' in comment:
                    table = comment.split("if-table-exists")[1].strip()
                    res = __execute_sql(
                        conn,
                        "select count(*) from information_schema.tables where table_schema='public' and table_name='{}'".format(table),
                        fetchone=True
                    )
                    if not res[0]:
                        continue
        try:
            print(line)
            __execute_sql(conn, line)
        except Exception:
            if critical:
                raise
            msg = traceback.format_exc()
            print("failed un-critical sql:", msg)

    remove_webassets(conn)

@db.command(name="dosync")
@click.argument("area", required=False)
@pass_config
def dosync(config, area):
    """
    help: Area defined in .access/config e.g. 'prod'
    """
    if not area:
        click.echo("Following areas available:")
        for area in get_areas():
            click.echo(area)
    access_config = get_config(area)

    compose = json.loads(__read_file(files['docker_compose']))
    volume = filter(lambda v: '/var/lib/postgresql/data' in v, compose['services']['postgres']['volumes'])[0]
    volume = volume.split(":")[0]

    __dc(['kill'] + ['postgres'])
    args = [
        '-v {volume}:/dest'.format(**locals()),
        'volumesyncer',
        '/usr/bin/rsync',
        '-arP',
        '{host}:{postgres_volume_dir}/_data/'.format(**access_config),
        '/dest/'
    ]
    __dcrun(args, interactive=True)
    __dc(['up', '-d'] + ['postgres'])


# @db.command(name="export-table")
# @click.argument('table', required=True)
# @pass_config
# def export_table(config, table):
    # dbname = config.dbname
    # conn = config.get_odoo_conn().clone(dbname=dbname)
    # from pudb import set_trace
    # set_trace()
    # __execute_sql(conn, "copy {} to stdout with csv delimiter ';'")
    # res = conn.fetchall()
    # return res


Commands.register(reset_db, 'reset-db')
