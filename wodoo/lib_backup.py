from codecs import ignore_errors
import time
import sys
import uuid
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
from .tools import put_appendix_into_file
from .tools import _dropdb
from .tools import remove_webassets
from .tools import __dc
from .tools import _execute_sql
from .tools import __rename_db_drop_target
from .tools import _remove_postgres_connections
from .tools import _get_dump_files
from .tools import _binary_zip
from .tools import autocleanpaper
from .tools import _shell_complete_file
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup

import inspect
import os
from pathlib import Path

current_dir = Path(
    os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
)

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


@backup.command(name="all")
@click.argument("filename", required=False)
@pass_config
@click.pass_context
def backup_all(ctx, config, filename):
    """
    Runs backup-db and backup-files
    """
    config.force = True
    filename = Path(filename or (config.dbname + ".db_and_files"))
    if len(filename.parts) == 1:
        filename = Path(config.dumps_path) / filename
    with autocleanpaper(Path(config.dumps_path) / str(uuid.uuid4())) as tmppath:
        filepath_db = ctx.invoke(backup_db, filename=tmppath / "db", dumptype="plain")
        filepath_files = ctx.invoke(backup_files, filename=tmppath / "files")
        assert filepath_db.parent == filepath_files.parent
        with autocleanpaper() as tmpfile:
            subprocess.check_call(
                [
                    "tar",
                    "cfz",
                    tmpfile,
                    "-C",
                    filepath_db.parent,
                    filepath_db.name,
                    filepath_files.name,
                ]
            )
            put_appendix_into_file("dump_all\n", tmpfile, filename)
    click.secho(f"Created dump-file {filename}", fg="green")


@backup.command(name="odoo-db")
@pass_config
@click.pass_context
@click.argument("filename", required=False, default="")
@click.option("--dbname", required=False)
@click.option("-T", "--exclude", multiple=True)
@click.option(
    "--column-inserts",
    is_flag=True,
    help="Makes restore slow but compatible with other databases",
)
@click.option(
    "--dumptype",
    type=click.Choice(["custom", "plain", "directory", "wodoobin"]),
    default="custom",
)
@click.option(
    "--pigz",
    is_flag=True,
)
@click.option(
    "-Z",
    "--compression",
    default=5,
)
@click.option("-j", "--worker", default=1)
def backup_db(
    ctx,
    config,
    filename,
    dbname,
    dumptype,
    column_inserts,
    exclude,
    pigz,
    compression,
    worker,
):
    filename = Path(
        filename or f"{config.project_name}.{config.dbname}.odoo" + ".dump.gz"
    )
    if len(filename.parts) == 1:
        filename = Path(config.dumps_path) / filename

    if dumptype == "wodoobin":
        if not config.run_postgres:
            abort(
                (
                    "Binary ZIP requires own postgres container. DB is also "
                    "stopped for that."
                )
            )
        conn = config.get_odoo_conn()
        version = None
        version = _get_postgres_version(conn)
        Commands.invoke(ctx, "stop", machines=["postgres"])
        path = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "volume",
                    "inspect",
                    f"{config.PROJECT_NAME}_odoo_postgres_volume",
                ]
            )
        )[0]["Mountpoint"]

        with autocleanpaper() as tempfile_zip:
            _binary_zip(path, tempfile_zip)

            put_appendix_into_file(f"WODOO_BIN\n{version}\n", tempfile_zip, filename)

        Commands.invoke(ctx, "up", daemon=True, machines=["postgres"])

    else:
        click.secho(f"Backup file will be stored there: {filename.parent}")
        cmd = [
            "run",
            "--rm",
            "--entrypoint",
            "python3 /usr/local/bin/postgres.py",
            "-v",
            f"{filename.parent}:/host/dumps2",
            "cronjobshell",
            "backup",
            dbname or config.DBNAME,
            config.DB_HOST,
            config.DB_PORT,
            config.DB_USER,
            config.DB_PWD,
            "/host/dumps2/" + filename.name,
            "--dumptype",
            dumptype,
            "--compression",
            str(compression),
            "-j",
            str(worker),
        ]
        for exclude in exclude:
            cmd += ["--exclude", exclude]
        if column_inserts:
            cmd += ["--column-inserts"]
        if pigz:
            cmd += ["--pigz"]

        res = __dc(config, cmd)
        if res:
            raise Exception("Backup failed!")
    return filename


@backup.command(name="files")
@click.argument("filename", required=False, default="")
@pass_config
def backup_files(config, filename):
    filepath = Path(filename or f"{config.project_name}.files.tar.gz")
    if len(filepath.parts) == 1:
        filepath = Path(config.dumps_path) / filepath

    if filepath.exists():
        # dont loose files
        __do_restore_files(config, filepath)

    files_dir = config.dirs["odoo_data_dir"] / "filestore" / config.dbname
    if not files_dir.exists():
        return
    subprocess.check_call(["tar", "cfz", filepath, "."], cwd=files_dir)
    __apply_dump_permissions(filepath)
    click.secho(f"Backup files done to {filepath}", fg="green")
    return filepath


def __get_default_backup_filename(config):
    return datetime.now().strftime(f"{config.project_name}.odoo.%Y%m%d%H%M%S.dump.gz")


@restore.command("show-dump-type")
@click.argument("filename")
@pass_config
def get_dump_type(config, filename):
    dump_type = _add_cronjob_scripts(config)["postgres"].__get_dump_type(filename)
    click.echo(dump_type)


@restore.command(name="list")
@pass_config
def list_dumps(config):
    rows = _get_dump_files()
    click.echo(tabulate(rows, ["Nr", "Filename", "Age", "Size"]))


@restore.command(name="files")
@click.argument("filename", required=True)
@pass_config
def restore_files(config, filename):
    __do_restore_files(config, filename)


def _get_postgres_version(conn):
    version = _execute_sql(conn, "select version()", fetchone=True)[0]
    version = version.split("(")[0].split(" ")[1]
    version = version.strip()
    click.secho(f"Identified version {version}", fg="green")
    return version


def _restore_wodoo_bin(ctx, config, filepath, verify):
    if not config.run_postgres:
        abort("WODOO-BIN files may only be restored if RUN_POSTGRES=1")
    click.secho(f"Unzipping {filepath}...", fg="yellow")
    with open(filepath, "rb") as file:
        content = file.read(1024)
        count_lineendings = 0
        cutoff = 0
        for i in range(len(content)):
            cutoff += 1
            if content[i] == ord(b"\n"):
                count_lineendings += 1
            if count_lineendings == 2:
                break
    if verify:
        click.secho(f"Verifying version postgres", fg="yellow")
        Commands.invoke(ctx, "up", daemon=True, machines=["postgres"])
        postgres_version = (
            content.decode("utf-8", errors="ignore").split("\n")[1].strip()
        )
        conn = config.get_odoo_conn()
        version = _get_postgres_version(conn)
        if version != postgres_version:
            abort(f"Version mismatch: {version} != {postgres_version}")
        click.secho(f"Versions match", fg="green")

    assert config.run_postgres
    Commands.invoke(ctx, "down")
    volume = json.loads(
        subprocess.check_output(
            [
                "docker",
                "volume",
                "inspect",
                f"{config.PROJECT_NAME}_odoo_postgres_volume",
            ],
            encoding="utf-8",
        )
    )
    mountpoint = volume[0]["Mountpoint"]
    click.secho(f"Identified mountpoint {mountpoint}", fg="yellow")
    with autocleanpaper() as scriptfile:
        scriptfile.write_text(
            (
                "#!/bin/bash\n"
                "set -e\n"
                f"rm -Rf '{mountpoint}'\n"
                f"mkdir '{mountpoint}'\n"
                f"cd '{mountpoint}'\n"
                f"tail '{filepath}' -c +{cutoff + 1} | "
                f"pigz -dc | tar x\n"
            )
        )
        for mode in ["", "sudo"]:
            try:
                subprocess.check_call(
                    list(filter(bool, [mode, "/bin/bash", scriptfile]))
                )
            except Exception:
                if mode:
                    raise
                click.secho(
                    "Retrying to restore the files in sudo mode - ignore previous errors please",
                    fg="yellow",
                )
            else:
                break
    Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)


@restore.command(name="odoo-db")
@click.argument(
    "filename", required=False, default="", shell_complete=_shell_complete_file
)
@click.option("--no-dev-scripts", default=False, is_flag=True)
@click.option("--no-remove-webassets", default=False, is_flag=True)
@click.option("-j", "--workers", default=5)
@click.option(
    "--verify", default=False, is_flag=True, help="Wodoo-bin: checks postgres version"
)
@click.option(
    "-X",
    "--exclude-tables",
    multiple=True,
    help="Exclude tables from restore like --exclude=mail_message",
)
@click.option("-v", "--verbose", is_flag=True)
@click.option(
    "--ignore-errors",
    is_flag=True,
    help="Example if some extensions are missing (replication)",
)
@pass_config
@click.pass_context
def restore_db(
    ctx,
    config,
    filename,
    no_dev_scripts,
    no_remove_webassets,
    verify,
    workers,
    exclude_tables,
    verbose,
    ignore_errors,
):
    if not filename:
        filename = _inquirer_dump_file(
            config, "Choose filename to restore", config.dbname
        )
    if not filename:
        return
    if not config.dbname:
        raise Exception("somehow dbname is missing")

    dumps_path = config.dumps_path
    BACKUPDIR = Path(dumps_path)
    filename_absolute = (BACKUPDIR / filename).absolute()
    del filename

    if not config.force:
        __restore_check(filename_absolute, config)

    dump_type = _add_cronjob_scripts(config)["postgres"].__get_dump_type(
        filename_absolute
    )

    DBNAME_RESTORING = config.dbname + "_restoring"
    if len(Path(filename_absolute).parts) > 1:
        dumps_path = Path(filename_absolute).parent
        filename = Path(filename_absolute).name

    if dump_type.startswith("dump_all"):
        with autocleanpaper() as tmpdir:
            with _add_cronjob_scripts(config)["postgres"].extract_dumps_all(
                tmpdir, filename_absolute
            ) as (dbfile, files_file):
                ctx.invoke(restore_files, filename=files_file)
                ctx.invoke(
                    restore_db,
                    filename=dbfile,
                    no_dev_scripts=no_dev_scripts,
                    no_remove_webassets=no_remove_webassets,
                )
                return

    if dump_type.startswith("wodoo_bin"):
        _restore_wodoo_bin(ctx, config, filename_absolute, verify)

    else:
        if config.run_postgres:
            postgres_name = f"{config.PROJECT_NAME}_run_postgres"
            client = docker.from_env()
            for container in client.containers.list(
                filters={"name": f"{postgres_name}"}
            ):
                container.kill()
                container.remove()

            try:
                Commands.invoke(ctx, "down")
            except Exception as ex:
                pass
            Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
        Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)
        conn = config.get_odoo_conn()
        dest_db = conn.dbname

        conn = conn.clone(dbname=DBNAME_RESTORING)
        with config.forced() as config:
            _dropdb(config, conn)

        _execute_sql(
            conn.clone(dbname="postgres"),
            (
                f"create database {DBNAME_RESTORING} "
                # "ENCODING 'unicode' "
                # "LC_COLLATE 'C' "
                # "TEMPLATE template0 "
                ";"
            ),
            notransaction=True,
        )
        effective_host_name = config.DB_HOST

        if config.devmode and not no_dev_scripts:
            click.echo("Option devmode is set, so cleanup-scripts are run afterwards")
        try:
            if config.use_docker:

                # if postgres docker is used, then make a temporary config to restart docker container
                # with external directory mapped; after that remove config
                if config.run_postgres:
                    __dc(config, ["kill", "postgres"])
                    __dc(
                        config,
                        [
                            "run",
                            "-d",
                            "--name",
                            f"{postgres_name}",
                            "--rm",
                            "--service-ports",
                            "-v",
                            f"{dumps_path}:/host/dumps2",
                            "postgres",
                        ],
                    )
                    Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)
                    effective_host_name = postgres_name

                cmd = [
                    "run",
                    "--rm",
                    "--entrypoint",
                    "python3 /usr/local/bin/postgres.py",
                ]

                parent_path_in_container = "/host/dumps2"
                cmd += [
                    "-v",
                    f"{dumps_path}:{parent_path_in_container}",
                ]
                cmd += [
                    "cronjobshell",
                    "restore",
                    DBNAME_RESTORING,
                    effective_host_name,
                    config.DB_PORT,
                    config.DB_USER,
                    config.DB_PWD,
                    f"{parent_path_in_container}/{filename}",
                    "-j",
                    str(workers),
                ]
                if ignore_errors:
                    cmd += ["--ignore-errors"]
                if exclude_tables:
                    cmd += [
                        "--exclude-tables",
                        ",".join(exclude_tables),
                    ]
                if verbose:
                    cmd += ["--verbose"]
                __dc(config, cmd)
            else:
                _add_cronjob_scripts(config)["postgres"]._restore(
                    DBNAME_RESTORING,
                    effective_host_name,
                    config.DB_PORT,
                    config.DB_USER,
                    config.DB_PWD,
                    Path(config.dumps_path) / filename,
                )

            from .lib_turnintodev import __turn_into_devdb

            if config.devmode and not no_dev_scripts:
                __turn_into_devdb(config, conn)
                if not no_remove_webassets:
                    remove_webassets(conn)
            __rename_db_drop_target(
                conn.clone(dbname="postgres"), DBNAME_RESTORING, config.dbname
            )
            _remove_postgres_connections(conn.clone(dbname=dest_db))

        finally:
            if config.run_postgres:
                # stop the run started postgres container; softly
                subprocess.check_output(["docker", "stop", postgres_name])
                try:
                    subprocess.check_output(["docker", "kill", postgres_name])
                except subprocess.CalledProcessError:
                    # ignore - stopped before
                    pass
                subprocess.check_output(["docker", "rm", "-f", postgres_name])

    if config.run_postgres:
        __dc(config, ["up", "-d", "postgres"])
        Commands.invoke(ctx, "wait_for_container_postgres")
        if config.devmode:
            Commands.invoke(ctx, "pghba_conf_wide_open")


def _add_cronjob_scripts(config):
    """
    Adds scripts from images/cronjobs/bin to sys path to be executed.
    """
    spec = importlib.util.spec_from_file_location(
        "bin", config.dirs["images"] / "cronjobs" / "bin" / "postgres.py"
    )
    postgres = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(postgres)
    return {
        "postgres": postgres,
    }


def _inquirer_dump_file(config, message, filter):
    BACKUPDIR = Path(config.dumps_path)
    __files = _get_dump_files(BACKUPDIR)
    filename = inquirer.prompt([inquirer.List("filename", message, choices=__files)])
    if filename:
        filename = filename["filename"][1]
        return filename


def _get_filestore_destination(config):
    files_dir = config.dirs["odoo_data_dir"] / "filestore" / config.dbname
    files_dir.mkdir(exist_ok=True, parents=True)
    return files_dir


def __do_restore_files(config, filepath):
    # https://askubuntu.com/questions/128492/is-there-a-way-to-tar-extract-without-clobbering
    # remove the postgres volume and reinit
    filepath = Path(filepath)
    if len(filepath.parts) == 1:
        filepath = Path(config.dumps_path) / filepath
    files_dir = _get_filestore_destination(config)
    subprocess.check_call(
        [
            "tar",
            "xzf",
            filepath,
        ],
        cwd=files_dir,
    )
    click.secho(f"Files restored from {filepath} to {files_dir}", fg="green")


def __restore_check(filepath, config):
    pass


def __apply_dump_permissions(filepath):
    def change(cmd, id):
        subprocess.check_call(["sudo", cmd, id, filepath])

    for x in [("DUMP_UID", "chown"), ("DUMP_GID", "chgrp")]:
        id = os.getenv(x[0])
        if id:
            change(x[1], id)


@restore.command()
@click.argument("filename", required=True, shell_complete=_shell_complete_file)
@pass_config
@click.pass_context
def odoo_sh(ctx, config, filename):
    pass
    with autocleanpaper() as tempfolder:
        filename = Path(filename).absolute()
        tempfolder.mkdir(exist_ok=True, parents=True)
        was_dir = os.getcwd()
        try:
            os.chdir(tempfolder)
            if not filename.exists():
                raise click.Abort(f"File does not exist: {tempfolder}")
            subprocess.check_call(["unzip", filename])
            sqlfile = tempfolder / "dump.sql"
            filestore = tempfolder / "filestore"

            if filestore.exists():
                filestore_dest = _get_filestore_destination(config)
                click.secho(f"Transferring files to {filestore_dest}")
                subprocess.check_call(
                    ["rsync", str(filestore) + "/", str(filestore_dest) + "/", "-ar"]
                )
            if sqlfile.exists():
                click.secho(f"Restoring db {sqlfile}")
                os.chdir(was_dir)
                Commands.invoke(ctx, "restore_db", filename=sqlfile)
        finally:
            os.chdir(was_dir)

Commands.register(backup_db)
Commands.register(restore_db)
