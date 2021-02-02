#!/usr/bin/python3
import gzip
import platform
import psycopg2
import pipes
import tempfile
import subprocess
from threading import Thread
import os
import click
from pathlib import Path
from datetime import datetime
import logging
FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

@click.group()
def postgres():
    pass

@postgres.command(name='exec')
@click.argument('dbname', required=True)
@click.argument('host', required=True)
@click.argument('port', required=True)
@click.argument('user', required=True)
@click.argument('password', required=True)
@click.argument('sql', required=True)
def execute(dbname, host, port, user, password, sql):
    with psycopg2.connect(
        host=host,
        database=dbname,
        port=port,
        user=user,
        password=password,
    ) as conn:
        conn.autocommit = True
        with conn.cursor() as cr:
            logger.info(f"executing sql: {sql}")
            cr.execute(sql)
            res = cr.fetchall()
            logger.info(res)
            return res


@postgres.command()
@click.argument('dbname', required=True)
@click.argument('host', required=True)
@click.argument('port', required=True)
@click.argument('user', required=True)
@click.argument('password', required=True)
@click.argument('filepath', required=True)
@click.option('--dumptype', type=click.Choice(["custom", "plain"]), default='custom')
def backup(dbname, host, port, user, password, filepath, dumptype):
    port = int(port)
    filepath = Path(filepath)
    os.environ['PGPASSWORD'] = password
    conn = psycopg2.connect(
        host=host,
        database=dbname,
        port=port,
        user=user,
        password=password,
    )
    click.echo(f"Backing up to {filepath}"
    try:
        cr = conn.cursor()
        cr.execute("SELECT (pg_database_size(current_database())) FROM pg_database")
        size = cr.fetchone()[0] * 0.7 # ct
        bytes = str(float(size)).split(".")[0]
        temp_filepath = filepath.with_name('.' + filepath.name)

        cmd = f'pg_dump --clean --no-owner -h "{host}" -p {port} -U "{user}" -Z0 -F{dumptype[0].lower()} {dbname} | pv -s {bytes} | pigz --rsyncable > {temp_filepath}'

        os.system(cmd)
        temp_filepath.replace(filepath)
    finally:
        conn.close()

@postgres.command()
@click.argument('dbname', required=True)
@click.argument('host', required=True)
@click.argument('port', required=True)
@click.argument('user', required=True)
@click.argument('password', required=True)
@click.argument('filepath', required=True)
def restore(dbname, host, port, user, password, filepath):
    _restore(dbname, host, port, user, password, filepath)

def _restore(dbname, host, port, user, password, filepath):
    click.echo(f"Restoring dump on {host}:{port} as {user}")
    os.environ['PGPASSWORD'] = password
    args = ["-h", host, "-p", str(port), "-U", user]
    PGRESTORE = [
        "pg_restore",
        "--no-owner",
        "--no-privileges",
        "--no-acl",
    ] + args
    PSQL = ["psql"] + args
    if not dbname:
        raise Exception("DBName missing")

    os.system(f"echo 'drop database if exists {dbname};' | psql {" ".join(args)} template1"
    os.system(f"echo 'create database {dbname};' | psql {" ".join(args)} template1"

    method = PGRESTORE
    needs_unzip = True

    dump_type = __get_dump_type(filepath)
    if dump_type == 'plain_text':
        needs_unzip = False
        method = PSQL
    elif dump_type == 'zipped_sql':
        method = PSQL
        needs_unzip = True
    elif dump_type == "zipped_pgdump":
        pass
    elif dump_type == "pgdump":
        needs_unzip = False
    else:
        raise Exception(f"not impl: {dump_type}")

    PREFIX = []
    if needs_unzip:
        PREFIX = [next(_get_file('gunzip'))]
    else:
        PREFIX = []
    started = datetime.now()
    click.echo("Restoring DB...")
    CMD = " " .join(pipes.quote(s) for s in ['pv', str(filepath)])
    CMD += " | "
    if PREFIX:
        CMD += " ".join(pipes.quote(s) for s in PREFIX)
        CMD += " | "
    CMD += " ".join(pipes.quote(s) for s in method)
    CMD += " "
    CMD += " ".join(pipes.quote(s) for s in [
        '-d',
        dbname,
    ])
    os.system(CMD)
    click.echo(f,f"Restore took {(datetime.now() - started).total_seconds())} seconds"

def __get_dump_type(filepath):
    MARKER = "PostgreSQL database dump"
    first_line = None
    zipped = False
    try:
        with gzip.open(filepath, 'r') as f:
            for line in f:
                first_line = line.decode('utf-8', errors='ignore')
                zipped = True
                break
    except Exception:
        with open(filepath, 'rb') as f:
            first_line = ""
            for i in range(2048):
                t = f.read(1)
                t = t.decode("utf-8", errors="ignore")
                first_line += t

    if first_line and zipped:
        if MARKER in first_line or first_line.strip() == '--':
            return 'zipped_sql'
        if first_line.startswith("PGDMP"):
            return "zipped_pgdump"
    elif first_line:
        if "PGDMP" in first_line:
            return 'pgdump'
        if MARKER in first_line:
            return "plain_text"
    return 'unzipped_pgdump'

def _get_file(filename):
    paths = [
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
    ]
    for x in paths:
        f = Path(x) / filename
        if f.exists():
            yield str(f)


if __name__ == '__main__':
    postgres()
