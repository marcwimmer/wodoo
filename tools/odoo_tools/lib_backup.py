import sys
import docker
import threading
import time
import json
import importlib.util
import re
from retrying import retry
import traceback
from threading import Thread
import subprocess
import pipes
import shutil
from datetime import datetime
import inquirer
import hashlib
import os
import tempfile
import click
from pathlib import Path
from .tools import _dropdb
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __dc, __dc_out
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import __get_dump_type
from .tools import _wait_postgres
from .tools import __dcrun
from .tools import _execute_sql
from .tools import _askcontinue
from .tools import __rename_db_drop_target
from .tools import _remove_postgres_connections
from .tools import _get_dump_files
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
try:
    import tabulate
except ImportError:
    click.echo("Failed to import python package: tabulate")


@cli.group(cls=AliasedGroup)
@pass_config
def backup(config):
    pass

@cli.group(cls=AliasedGroup)
@pass_config
def restore(config):
    pass


@backup.command(name='all')
@pass_config
@click.pass_context
def backup_all(ctx, config):
    """
    Runs backup-db and backup-files
    """
    config.force = True
    ctx.invoke(backup_db)
    ctx.invoke(backup_files)


@backup.command(name='odoo-db')
@pass_config
@click.pass_context
@click.argument('filename', required=False, default="")
@click.option('--dbname', required=False)
@click.option('--column-inserts', is_flag=True)
@click.option('--dumptype', type=click.Choice(["custom", "plain", "directory"]), default='custom')
def backup_db(ctx, config, filename, dbname, dumptype, column_inserts):
    filename = Path(filename or f'{config.project_name}.{config.dbname}.odoo' + '.dump.gz')
    if len(filename.parts) == 1:
        filename = Path(config.dumps_path) / filename
    click.secho(f"Backup file will be stored there: {filename.parent}")
    cmd = [
        'run',
        '--rm',
        '-v',
        f'{filename.parent}:/host/dumps2',
        'cronjobshell',
        'postgres.py',
        'backup',
        dbname or config.DBNAME,
        config.DB_HOST,
        config.DB_PORT,
        config.DB_USER,
        config.DB_PWD,
        '/host/dumps2/' + filename.name,
        "--dumptype", dumptype,
    ]
    if column_inserts:
        cmd += [
            "--column-inserts"
        ]

    res = __dc(cmd)
    if res:
        raise Exception('Backup failed!')


@backup.command(name='files')
@click.argument('filename', required=False, default="")
@pass_config
def backup_files(config, filename):
    filepath = Path(filename or f"{config.project_name}.files.tar.gz")
    if len(filepath.parts) == 1:
        filepath = Path(config.dumps_path) / filepath

    if filepath.exists():

        second = filepath.with_suffix(filepath.suffix + '.bak')
        second.exists() and second.unlink()
        shutil.move(filepath, second)

    files_dir = config.dirs['odoo_data_dir'] / 'filestore' / config.dbname
    if not files_dir.exists():
        return
    subprocess.check_call([
        'tar',
        'cfz',
        filepath,
        '.'
    ], cwd=files_dir)
    __apply_dump_permissions(filepath)
    click.secho(f"Backup files done to {filepath}", fg='green')

def __get_default_backup_filename(config):
    return datetime.now().strftime(f"{config.project_name}.odoo.%Y%m%d%H%M%S.dump.gz")

@restore.command('show-dump-type')
@pass_config
def get_dump_type(config, filename):
    BACKUPDIR = Path(config.dumps_path)
    filename = _inquirer_dump_file(config, '', config.dbname)
    if filename:
        dump_file = BACKUPDIR / filename
        dump_type = __get_dump_type(dump_file)
        click.echo(dump_type)

@restore.command(name='list')
@pass_config
def list_dumps(config):
    rows = _get_dump_files()
    click.echo(tabulate(rows, ["Nr", 'Filename', 'Age', 'Size']))

@restore.command(name='files')
@click.argument('filename', required=True)
def restore_files(filename):
    __do_restore_files(filename)

@restore.command(name='odoo-db')
@click.argument('filename', required=False, default='')
@click.option('--latest', default=False, is_flag=True, help="Restore latest dump")
@click.option('--no-dev-scripts', default=False, is_flag=True)
@pass_config
@click.pass_context
def restore_db(ctx, config, filename, latest, no_dev_scripts):
    if not filename:
        filename = _inquirer_dump_file(config, "Choose filename to restore", config.dbname, latest=latest)
    if not filename:
        return
    if config.run_postgres:
        postgres_name = f"{config.PROJECT_NAME}_run_postgres"
        client = docker.from_env()
        for container in client.containers.list(filters={'name': f'{postgres_name}'}):
            container.kill()
            container.remove()

        Commands.invoke(ctx, 'down')
        Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
    Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
    conn = config.get_odoo_conn()
    dest_db = conn.dbname

    dumps_path = config.dumps_path

    if len(Path(filename).parts) > 1:
        dumps_path = Path(filename).parent
        filename = Path(filename).name


    BACKUPDIR = Path(dumps_path)
    filename = (BACKUPDIR / filename).absolute()

    if not config.force and not latest:
        __restore_check(filename, config)

    DBNAME_RESTORING = config.dbname + "_restoring"

    if not config.dbname:
        raise Exception("somehow dbname is missing")

    conn = conn.clone(dbname=DBNAME_RESTORING)
    with config.forced() as config:
        _dropdb(config, conn)

    _execute_sql(
        conn.clone(dbname="postgres"),
        "create database {};".format(DBNAME_RESTORING),
        notransaction=True
    )
    effective_host_name = config.DB_HOST

    if config.devmode and not no_dev_scripts:
        click.echo("Option devmode is set, so cleanup-scripts are run afterwards")
    try:

        if config.use_docker:

            # if postgres docker is used, then make a temporary config to restart docker container
            # with external directory mapped; after that remove config
            if config.run_postgres:
                __dc(['kill', 'postgres'])
                __dc(['run', '-d', '--name', f'{postgres_name}', '--rm', '--service-ports', '-v', f'{dumps_path}:/host/dumps2', 'postgres'])
                Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
                effective_host_name = postgres_name

            cmd = [
                'run',
                '--rm',
            ]

            parent_path_in_container = '/host/dumps2'
            cmd += [
                "-v",
                f"{dumps_path}:{parent_path_in_container}",
            ]

            cmd += [
                'cronjobshell', 'postgres.py', 'restore',
                DBNAME_RESTORING, effective_host_name, config.DB_PORT,
                config.DB_USER, config.DB_PWD, f'{parent_path_in_container}/{filename.name}',
            ]
            __dc(cmd)
        else:
            _add_cronjob_scripts(config)['postgres']._restore(
                DBNAME_RESTORING, effective_host_name, config.DB_PORT,
                config.DB_USER, config.DB_PWD, Path(config.dumps_path) / filename,
            )

        from .lib_db import __turn_into_devdb
        if config.devmode and not no_dev_scripts:
            __turn_into_devdb(config, conn)
        __rename_db_drop_target(conn.clone(dbname='postgres'), DBNAME_RESTORING, config.dbname)
        _remove_postgres_connections(conn.clone(dbname=dest_db))

    finally:
        if config.run_postgres:
            # stop the run started postgres container; softly
            subprocess.check_output(['docker', 'stop', postgres_name])
            try:
                subprocess.check_output(['docker', 'kill', postgres_name])
            except subprocess.CalledProcessError:
                # ignore - stopped before
                pass
            subprocess.check_output(['docker', 'rm', '-f', postgres_name])

    if config.run_postgres:
        __dc(['up', '-d', 'postgres'])
        Commands.invoke(ctx, 'wait_for_container_postgres')

def _add_cronjob_scripts(config):
    """
    Adds scripts from images/cronjobs/bin to sys path to be executed.
    """
    spec = importlib.util.spec_from_file_location("bin", config.dirs['images'] / 'cronjobs' / 'bin' / 'postgres.py')
    postgres = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(postgres)
    print(postgres.__get_dump_type)
    return {
        'postgres': postgres,
    }

def _inquirer_dump_file(config, message, filter, latest=False):
    BACKUPDIR = Path(config.dumps_path)
    __files = _get_dump_files(BACKUPDIR)
    if latest:
        if not __files:
            click.secho("No dump file found - option latest given.", fg='red')
            sys.exit(1)
        return __files[0][1]
    filename = inquirer.prompt([inquirer.List('filename', message, choices=__files)])
    if filename:
        filename = filename['filename'][1]
        return filename

def __do_restore_files(config, filepath):
    # remove the postgres volume and reinit
    if filepath.startswith("/"):
        raise Exception("No absolute path allowed")
    filepath = Path(filepath)
    files_dir = config.dirs['odoo_data_dir'] / config.dbname
    subprocess.check_call([
        'tar',
        'xfz',
        filepath,
    ], cwd=files_dir)
    click.secho("Files restored {}".format(filepath), fg='green')

def __restore_check(filepath, config):
    pass

def __apply_dump_permissions(filepath):

    def change(cmd, id):
        subprocess.check_call([
            "sudo",
            cmd,
            id,
            filepath
        ])

    for x in [
        ("DUMP_UID", 'chown'),
        ("DUMP_GID", 'chgrp')
    ]:
        id = os.getenv(x[0])
        if id:
            change(x[1], id)


Commands.register(backup_db)
Commands.register(restore_db)
