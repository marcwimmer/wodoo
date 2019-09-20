#!/usr/bin/python3
import psycopg2
import pipes
import tempfile
import subprocess
from threading import Thread
import os
import click
from pathlib import Path
from datetime import datetime

@click.group()
def postgres():
    pass

@postgres.command()
@click.argument('dbname', required=True)
@click.argument('host', required=True)
@click.argument('port', required=True)
@click.argument('user', required=True)
@click.argument('password', required=True)
@click.argument('filepath', required=True)
def backup(dbname, host, port, user, password, filepath):
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
    click.echo("Backing up to {}".format(filepath))
    try:
        cr = conn.cursor()
        cr.execute("SELECT (pg_database_size(current_database())) FROM pg_database")
        size = cr.fetchone()[0] * 0.7 # ct
        bytes = str(float(size)).split(".")[0]
        temp_filepath = filepath.with_name('.' + filepath.name)

        cmd = 'pg_dump --no-owner -h "{host}" -p {port} -U "{user}" -Z0 -Fc {dbname} | pv -s {bytes} | pigz --rsyncable > {filepath}'.format(
            host=host,
            port=port,
            user=user,
            dbname=dbname,
            bytes=bytes,
            filepath=temp_filepath,
        )

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
    click.echo("Restoring dump on {}:{} as {}".format(host, port, user))
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

    os.system("echo 'drop database if exists {};' | psql {} template1".format(dbname, " ".join(args)))
    os.system("echo 'create database {};' | psql {} template1".format(dbname, " ".join(args)))

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
        raise Exception("not impl: {}".format(dump_type))

    PREFIX = []
    if needs_unzip:
        PREFIX = ["/bin/gunzip"]
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
    click.echo("Restore took {} seconds".format((datetime.now() - started).seconds))

def __get_dump_type(filepath):
    temp = Path(tempfile.mktemp(suffix='.check'))
    MARKER = "PostgreSQL database dump"
    FNULL = open(os.devnull, 'w')
    proc = subprocess.Popen(['gunzip', '-c', filepath], stdout=subprocess.PIPE, stderr=FNULL, bufsize=1)

    def reader(proc, pipe):
        try:
            lines = 0
            with pipe:
                for line in iter(pipe.readline, ''):
                    with temp.open('a') as f:
                        f.write(line.decode("utf-8", errors='ignore'))
                        lines += 1
                        if lines > 20:
                            break
        finally:
            if not proc.returncode:
                proc.kill()

    Thread(target=reader, args=[proc, proc.stdout]).start()
    proc.wait()

    if temp.exists() and temp.stat().st_size:
        content = temp.read_text()
        if MARKER in content:
            return 'zipped_sql'
        if content.startswith("PGDMP"):
            return "zipped_pgdump"
    with open(filepath, 'rb') as f:
        content = f.read(2048)
        content = content.decode('utf-8', errors='ignore')
        if "PGDMP" in content:
            return 'pgdump'
        if MARKER in content:
            return "plain_text"
    return 'unzipped_pgdump'


if __name__ == '__main__':
    postgres()
