from codecs import ignore_errors
from .tools import abort
import sys
import docker
import json
import importlib.util
from retrying import retry
import traceback
from threading import Thread
import subprocess
import shutil
from datetime import datetime
import inquirer
import os
import click
from pathlib import Path
from .tools import _dropdb
from .tools import remove_webassets
from .tools import __dc
from .tools import _execute_sql
from .tools import __rename_db_drop_target
from .tools import _remove_postgres_connections
from .tools import _get_dump_files
from .tools import _binary_zip
from .tools import autocleanpaper
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
@click.option('--dumptype', type=click.Choice([
    "custom", "plain", "directory", "wodoobin"]), default='custom')
def backup_db(ctx, config, filename, dbname, dumptype, column_inserts):
    filename = Path(filename or f'{config.project_name}.{config.dbname}.odoo' + '.dump.gz')
    if len(filename.parts) == 1:
        filename = Path(config.dumps_path) / filename

    if dumptype == 'wodoobin':
        if not config.run_postgres:
            abort((
                "Binary ZIP requires own postgres container. DB is also "
                "stopped for that."
            ))
        conn = config.get_odoo_conn()
        version = _get_postgres_version(conn)
        Commands.invoke(ctx, 'stop', machines=['postgres'])
        path = json.loads(subprocess.check_output([
            "docker", 'volume', 'inspect',
            f'{config.PROJECT_NAME}_odoo_postgres_volume',
        ]))[0]['Mountpoint']

        with autocleanpaper() as tempfile_zip:
            _binary_zip(path, tempfile_zip)

            with autocleanpaper() as tempfile:
                tempfile.write_text(f"WODOO_BIN\n{version}\n")
                os.system(f"cat {tempfile} {tempfile_zip} > {filename}")

        Commands.invoke(ctx, 'up', daemon=True, machines=['postgres'])

    else:

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
@click.argument('filename')
@pass_config
def get_dump_type(config, filename):
    BACKUPDIR = Path(config.dumps_path)
    if not filename:
        filename = _inquirer_dump_file(config, '', config.dbname)
    if filename:
        dump_file = BACKUPDIR / filename
        dump_type = _add_cronjob_scripts(config)['postgres'].__get_dump_type(dump_file)
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


def _get_postgres_version(conn):
    version = _execute_sql(conn, "select version()", fetchone=True)[0]
    version = version.split("(")[0].split(" ")[1]
    version = version.strip()
    click.secho(f"Identified version {version}", fg='green')
    return version

def _restore_wodoo_bin(ctx, config, filepath):
    if not config.run_postgres:
        abort("WODOO-BIN files may only be restored if RUN_POSTGRES=1")
    Commands.invoke(ctx, 'up', daemon=True, machines=['postgres'])
    with open(filepath, 'rb') as file:
        content = file.read(1024)
        count_lineendings = 0
        cutoff = 0
        for i in range(len(content)):
            cutoff += 1
            if content[i] == ord(b'\n'):
                count_lineendings += 1
            if count_lineendings == 2:
                break
    postgres_version = content.decode(
        'utf-8', errors='ignore').split("\n")[1].strip()
    conn = config.get_odoo_conn()
    version = _get_postgres_version(conn)
    if version != postgres_version:
        abort(f"Version mismatch: {version} != {postgres_version}")

    assert config.run_postgres
    Commands.invoke(ctx, 'down')
    volume = json.loads(subprocess.check_output([
        "docker", "volume", "inspect",
        f"{config.PROJECT_NAME}_odoo_postgres_volume"], encoding='utf-8'))
    mountpoint = volume[0]['Mountpoint']
    with autocleanpaper() as scriptfile:
        scriptfile.write_text((
            "#!/bin/bash\n"
            "set -ex\n"
            f"rm -Rf '{mountpoint}'\n"
            f"mkdir '{mountpoint}'\n"
            f"cd '{mountpoint}'\n"
            f"dd if={filepath} bs=1 skip={cutoff} | "
            f"tar Jx\n"
        ))
        subprocess.check_call(["/bin/bash", scriptfile])
    Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)

@restore.command(name='odoo-db')
@click.argument('filename', required=False, default='')
@click.option('--latest', default=False, is_flag=True, help="Restore latest dump")
@click.option('--no-dev-scripts', default=False, is_flag=True)
@click.option('--no-remove-webassets', default=False, is_flag=True)
@pass_config
@click.pass_context
def restore_db(ctx, config, filename, latest, no_dev_scripts, no_remove_webassets):
    if not filename:
        filename = _inquirer_dump_file(config, "Choose filename to restore", config.dbname, latest=latest)
    if not filename:
        return
    if not config.dbname:
        raise Exception("somehow dbname is missing")

    dumps_path = config.dumps_path
    BACKUPDIR = Path(dumps_path)
    filename_absolute = (BACKUPDIR / filename).absolute()
    del filename

    if not config.force and not latest:
        __restore_check(filename_absolute, config)

    dump_type = _add_cronjob_scripts(config)['postgres'].__get_dump_type(
        filename_absolute)

    DBNAME_RESTORING = config.dbname + "_restoring"
    if len(Path(filename_absolute).parts) > 1:
        dumps_path = Path(filename_absolute).parent
        filename = Path(filename_absolute).name

    if dump_type.startswith("wodoo_bin"):
        _restore_wodoo_bin(ctx, config, filename_absolute)

    else:
        if config.run_postgres:
            postgres_name = f"{config.PROJECT_NAME}_run_postgres"
            client = docker.from_env()
            for container in client.containers.list(
                    filters={'name': f'{postgres_name}'}):
                container.kill()
                container.remove()

            Commands.invoke(ctx, 'down')
            Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
        Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
        conn = config.get_odoo_conn()
        dest_db = conn.dbname

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
                    config.DB_USER, config.DB_PWD, f'{parent_path_in_container}/{filename}',
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
                if not no_remove_webassets:
                    remove_webassets(conn)
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
