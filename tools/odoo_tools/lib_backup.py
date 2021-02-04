import sys
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
from .tools import __dc
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import __get_dump_type
from .tools import _start_postgres_and_wait
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
    ctx.invoke(backup_db, non_interactive=True)
    ctx.invoke(backup_files)
    ctx.invoke(backup_calendar)

@backup.command(name='calendar')
@pass_config
def backup_calendar(config):
    if not config.run_calendar:
        return
    cmd = [
        'run',
        'cronjobshell',
        'postgres.py',
        'backup',
        config.CALENDAR_DB_NAME,
        config.CALENDAR_DB_HOST,
        config.CALENDAR_DB_PORT,
        config.CALENDAR_DB_USER,
        config.CALENDAR_DB_PWD,
        '/host/dumps/' + f'{config.project_name}.calendar' + '.dump.gz',
    ]
    __dc(cmd)


@backup.command(name='odoo-db')
@pass_config
@click.pass_context
@click.argument('filename', required=False, default="")
@click.option('--dbname', required=False)
@click.option('--dumptype', type=click.Choice(["custom", "plain", "directory"]), default='custom')
def backup_db(ctx, config, filename, dbname, dumptype):
    filename = filename or f'{config.project_name}.{config.dbname}.odoo' + '.dump.gz'
    cmd = [
        'run',
        'cronjobshell',
        'postgres.py',
        'backup',
        dbname or config.DBNAME,
        config.DB_HOST,
        config.DB_PORT,
        config.DB_USER,
        config.DB_PWD,
        '/host/dumps/' + filename,
        "--dumptype", dumptype,
    ]
    __dc(cmd)


@backup.command(name='files')
@pass_config
def backup_files(config):
    BACKUPDIR = Path(config.dumps_path)
    BACKUP_FILENAME = f"{config.project_name}.files.tar.gz"
    BACKUP_FILEPATH = config.dirs['backup_dir'] / BACKUP_FILENAME

    if BACKUP_FILEPATH.exists():
        second = BACKUP_FILENAME + ".bak"
        second_path = BACKUPDIR / second
        if second_path.exists():
            second_path.unlink()
        shutil.move(BACKUP_FILEPATH, second_path)
        del second
        del second_path
    files_dir = config.dirs['odoo_data_dir'] / config.dbname
    if not files_dir.exists():
        return
    subprocess.check_call([
        'tar',
        'cfz',
        BACKUP_FILEPATH,
        '.'
    ], cwd=files_dir)
    __apply_dump_permissions(BACKUP_FILEPATH)
    click.secho("Backup files done to {}".format(BACKUP_FILENAME), fg='green')

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

@restore.command(name="calendar")
@click.argument('filename', required=True)
@pass_config
@click.pass_context
def restore_calendar_db(ctx, config, filename):
    filename = Path(filename)

    __dc([
        'run',
        'cronjobshell',
        'postgres.py',
        'restore',
        config.CALENDAR_DB_NAME,
        config.CALENDAR_DB_HOST,
        config.CALENDAR_DB_PORT,
        config.CALENDAR_DB_USER,
        config.CALENDAR_DB_PWD,
        '/host/dumps/{}'.format(filename.name),
    ])

@restore.command(name='odoo-db')
@click.argument('filename', required=False, default='')
@click.option('--latest', default=False, is_flag=True, help="Restore latest dump")
@click.option('--no-dev-scripts', default=False, is_flag=True)
@pass_config
@click.pass_context
def restore_db(ctx, config, filename, latest, no_dev_scripts):
    conn = config.get_odoo_conn()
    dest_db = conn.dbname

    if config.devmode and not no_dev_scripts:
        click.echo("Option devmode is set, so cleanup-scripts are run afterwards")

    if not filename:
        filename = _inquirer_dump_file(config, "Choose filename to restore", config.dbname, latest=latest)
    if not filename:
        return

    BACKUPDIR = Path(config.dumps_path)
    filename = BACKUPDIR / filename
    if not config.force and not latest:
        __restore_check(filename, config)

    DBNAME_RESTORING = config.dbname + "_restoring"

    if not config.dbname:
        raise Exception("somehow dbname is missing")

    Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
    conn = conn.clone(dbname=DBNAME_RESTORING)
    with config.forced() as config:
        _dropdb(config, conn)

    _execute_sql(
        conn.clone(dbname="template1"),
        "create database {};".format(DBNAME_RESTORING),
        notransaction=True
    )

    if config.use_docker:
        __dc([
            'run',
            'cronjobshell',
            'postgres.py',
            'restore',
            DBNAME_RESTORING,
            config.db_host,
            config.db_port,
            config.db_user,
            config.db_pwd,
            '/host/dumps/{}'.format(filename.name),
        ])
    else:
        _add_cronjob_scripts(config)['postgres']._restore(
            DBNAME_RESTORING,
            config.db_host,
            config.db_port,
            config.db_user,
            config.db_pwd,
            Path(config.dumps_path) / filename,
        )

    from .lib_db import __turn_into_devdb
    if config.devmode and not no_dev_scripts:
        __turn_into_devdb(config, conn)
    __rename_db_drop_target(conn.clone(dbname='template1'), DBNAME_RESTORING, config.dbname)
    _remove_postgres_connections(conn.clone(dbname=dest_db))

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
    dumpname = filepath.name

    if config.dbname not in dumpname and not config.force:
        click.secho("The dump-name \"{}\" should somehow match the current database \"{}\", which isn't.".format(
            dumpname,
            config.dbname,
        ), fg='red')
        sys.exit(1)

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
