import arrow
import re
from retrying import retry
import docker
import traceback
import humanize
from threading import Thread
import subprocess
import tabulate
import pipes
import shutil
from datetime import datetime
import inquirer
import hashlib
import os
import tempfile
import click
from pathlib import Path
from .tools import DBConnection
from .tools import _dropdb
from .tools import __backup_postgres
from .tools import __postgres_restore
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __read_file
from .tools import __dc
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import __get_dump_type
from .tools import __start_postgres_and_wait
from .tools import __dcrun
from .tools import __execute_sql
from .tools import __set_db_ownership
from .tools import _askcontinue
from .tools import __rename_db_drop_target
from .tools import __remove_postgres_connections
from .tools import _get_dump_files
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

BACKUPDIR = Path("/host/dumps")

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
def backup_calendar(config, filename=None):
    if not config.run_calendar:
        return
    filename = filename or datetime.now().strftime("{}.calendar.%Y%m%d%H%M%S.dump.gz".format(config.customs))
    filepath = BACKUPDIR / filename
    conn = DBConnection(
        dbname=config.calendar_db_name,
        host=config.calendar_db_host,
        port=config.calendar_db_port,
        user=config.calendar_db_user,
        pwd=config.calendar_db_pwd
    )
    __backup_postgres(
        conn,
        filepath,
    )


@backup.command(name='odoo-db')
@click.argument('filename', required=False, default='')
@click.option('--non-interactive', is_flag=True)
@pass_config
@click.pass_context
def backup_db(ctx, config, filename, non_interactive):
    if not filename:
        if config.devmode:
            if not non_interactive:
                answer = inquirer.prompt([inquirer.Text('filename', message="Filename", default=__get_default_backup_filename(config))])
                if not answer:
                    return
                filename = answer['filename']
        else:
            customs = config.customs
            date = arrow.get()
            filename = config.db_odoo_fileformat.format(customs=customs, date=date)

    filename = filename or __get_default_backup_filename(config)

    if filename.startswith("/"):
        raise Exception("No slash for backup filename allowed")
    click.echo("Databasename is " + config.dbname)
    filepath = BACKUPDIR / filename
    if filepath.exists():
        filepath.unlink()
    __start_postgres_and_wait(config)

    conn = config.get_odoo_conn()
    __backup_postgres(
        conn,
        filepath,
    )

    __apply_dump_permissions(filepath)

    click.echo("Dumped to {}".format(filepath))

@backup.command(name='files')
@pass_config
def backup_files(config):
    BACKUP_FILENAME = "{CUSTOMS}.files.tar.gz".format(CUSTOMS=config.customs)
    BACKUP_FILEPATH = BACKUPDIR / BACKUP_FILENAME

    if BACKUP_FILEPATH.exists():
        second = BACKUP_FILENAME + ".bak"
        second_path = BACKUPDIR / second
        if second_path.exists():
            second_path.unlink()
        shutil.move(BACKUP_FILEPATH, second_path)
        del second
        del second_path
    __dcrun(["odoo", "/odoolib/backup_files.py", BACKUP_FILENAME])
    __apply_dump_permissions(BACKUP_FILEPATH)
    click.echo("Backup files done to {}".format(BACKUP_FILENAME))

def __get_default_backup_filename(config):
    return datetime.now().strftime("{}.odoo.%Y%m%d%H%M%S.dump.gz".format(config.customs))

@restore.command('show-dump-type')
@pass_config
def get_dump_type(config, filename):
    filename = _inquirer_dump_file(config)
    if filename:
        dump_file = BACKUPDIR / filename
        dump_type = __get_dump_type(dump_file)
        click.echo(dump_type)

@restore.command(name='list')
@pass_config
def list_dumps(config):
    rows = _get_dump_files(fnfilter=config.dbname)
    click.echo(tabulate(rows, ["Nr", 'Filename', 'Age', 'Size']))

@restore.command(name='files')
@click.argument('filename', required=True)
def restore_files(filename):
    __do_restore_files(filename)


@restore.command(name='odoo-db')
@click.argument('filename', required=False, default='')
@pass_config
@click.pass_context
def restore_db(ctx, config, filename):
    conn = config.get_odoo_conn()
    dest_db = conn.dbname
    dev = False

    if config.allow_restore_dev:
        if not config.force:
            questions = [
                inquirer.Confirm('dev', message="Restore as development database?", default=True)
            ]
            answers = inquirer.prompt(questions)
            dev = answers['dev']
        else:
            config.dev = True

    if dev:
        click.echo("Option DEV-DB is set, so cleanup-scripts are run afterwards")

    if not filename:
        filename = _inquirer_dump_file(config, "Choose filename to restore")
    if not filename:
        return

    filename = BACKUPDIR / filename
    if not config.force:
        __restore_check(filename, config)
    if config.devmode and not dev:
        _askcontinue(config, "DEVMODE ist set - really restore as normal db? Not using restore-dev-db?")

    DBNAME_RESTORING = config.dbname + "_restoring"

    if not config.dbname:
        raise Exception("somehow dbname is missing")

    Commands.invoke(ctx, 'wait_for_container_postgres')
    conn = conn.clone(dbname=DBNAME_RESTORING)
    with config.forced() as config:
        _dropdb(config, conn)
    __postgres_restore(
        conn,
        BACKUPDIR / filename,
    )
    from .lib_db import __turn_into_devdb
    if dev:
        __turn_into_devdb(conn)
    __rename_db_drop_target(conn.clone(dbname='template1'), DBNAME_RESTORING, config.dbname)
    __remove_postgres_connections(conn.clone(dbname=dest_db))

def _inquirer_dump_file(config, message):
    __files = _get_dump_files(BACKUPDIR, fnfilter=config.dbname)
    filename = inquirer.prompt([inquirer.List('filename', message, choices=__files)])
    if filename:
        filename = filename['filename'][1]
        return filename

def __do_restore_files(filepath):
    # remove the postgres volume and reinit
    if filepath.startswith("/"):
        raise Exception("No absolute path allowed")
    filepath = Path(filepath)
    __dcrun(['odoo', '/odoolib/restore_files.py', filepath.name])

def __restore_check(filepath, config):
    dumpname = filepath.name

    if config.dbname not in dumpname and not config.force:
        raise Exception("The dump-name \"{}\" should somehow match the current database \"{}\", which isn't.".format(
            dumpname,
            config.dbname,
        ))

def __reset_postgres_container(ctx, config):
    # remove the postgres volume and reinit
    if config.run_postgres:
        Commands.invoke(ctx, 'kill', machines='postgres', brutal=True)
        if config.run_postgres_in_ram:
            pass
        else:
            click.echo("Resettings postgres - killing data - not reversible")
            VOLUMENAME = "{}_postgresdata".format(config.customs)
            docker_client = docker.from_env()

            @retry(wait_random_min=500, wait_random_max=800, stop_max_delay=30000)
            def remove_volume():
                for volume in docker_client.volumes.list():
                    if volume.name == VOLUMENAME:
                        try:
                            Commands.invoke(ctx, 'kill', brutal=True)
                            __dc(["rm", "-f"]) # set volume free
                            volume.remove()
                        except Exception as e:
                            click.echo(e)
                            if hasattr(e, 'explanation'):
                                exp = e.explanation

                                if 'volume is in use' in e:
                                    container_id = re.findall(r'\[([^\]]*)\]', exp)[0]
                                    __system(["docker", "rm", container_id])
                            return None
                return True
            remove_volume()
            __dcrun(['-e', 'INIT=1', 'postgres', '/entrypoint2.sh'])
        __start_postgres_and_wait(config)


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
