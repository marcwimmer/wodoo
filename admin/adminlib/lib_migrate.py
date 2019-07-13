from pathlib import Path
import traceback
from datetime import datetime
import logging
import pickle
import base64
import shutil
import hashlib
import os
import tempfile
import click
from logging import FileHandler
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __execute_sql

def _migrate(ctx, config, log_file, from_version, to_version, SETTINGS_D_FILE, no_auto_backup=False, git_clean=True, debug=False, module='all', pull_latest=False):
    """

    Migration Script

    For Debugging OCA Migration script walk into /repos/Openupgrade and edit code.
    Provide parameter --no-git-clean then, otherwise traces/changes are removed.


    """
    CONFIG_FILE = '/home/odoo/config_migration'
    BASE_PATH = "/opt/odoo_home/repos/OpenUpgrade/" # must match in container

    def prepareCommand(cmd, module):
        def repl(s):
            s = s.format(
                configfile=CONFIG_FILE,
                db=config.dbname,
                module=module,
            )
            return s
        cmd = [repl(x) for x in cmd]
        cmd = pickle.dumps(cmd)
        cmd = base64.b64encode(cmd)
        return cmd

    def connect_db():
        import psycopg2
        return psycopg2.connect(
            dbname=config.dbname,
            user=config.db_user,
            host=config.db_host,
            port=long(config.db_port),
            password=config.db_pwd,
        )

    def __check_for_dangling_modules():
        conn = connect_db()
        cr = conn.cursor()
        cr.execute("select count(*) from ir_module_module where state like 'to install'")  # to upgrade seems to be ok
        if cr.fetchone()[0]:
            Commands.invoke(ctx, 'progress')
            raise Exception("Found dangling modules!")
        conn.close()

    def __run_before_after(type, version, debug, module, logger):
        click.echo("Running {} processes {}".format(type, version))
        cmd = (
            "/usr/bin/python",
            "/run_migration.py",
            type,
        )
        if module == 'all' and not debug:
            Commands.invoke(ctx, 'run', machine='odoo', args=cmd, logger=logger, volume=None)
        elif debug:
            answer = raw_input("Run {} sql/py? [Y/n]".format(type))
            if not answer or answer in ['Y', 'y']:
                Commands.invoke(ctx, 'runbash', machine='odoo', args=cmd, logger=logger)

    def __run_migration(migrations, git_clean, version, debug, module, logger, pull_latest):
        click.echo("Starting Openupgrade Migration to {}".format(version))
        cmd = (
            "/usr/bin/python",
            "/opt/migrate.sh",
            migrations[version]['branch'],
            prepareCommand(migrations[version]['cmd'], module=module),
            ','.join(str(BASE_PATH / x) for x in migrations[version]['addons_paths']),
            version,
            '1' if git_clean else '0',
            '1' if pull_latest else '0',
        )
        if debug:
            Commands.invoke(ctx, 'runbash', machine='odoo', args=cmd)
        else:
            Commands.invoke(ctx, 'run', machine='odoo', args=cmd, logger=logger, interactive=True, volume=None)  # interactive true: nice colors of [ERROR]

    """

    :param pull_latest: if true, then git pull is done in OpenUpgrade

    """
    from . import MyConfigParser
    from_version = str(float(from_version))
    to_version = str(float(to_version))

    # Make sure that RUN_MIGRATION is temporarily set to 1
    settings = MyConfigParser(SETTINGS_D_FILE)
    settings.clear()
    settings['RUN_MIGRATION'] = '1'
    settings.write()

    FORMAT = '[%(levelname)s] %(asctime)s\t%(message)s'
    logging.basicConfig(filename="/dev/stdout", format=FORMAT)
    logging.getLogger().setLevel(logging.DEBUG)
    logger = logging.getLogger('')  # root handler
    formatter = logging.Formatter(FORMAT)

    if log_file.exists():
        os.unlink(log_file)
    rh = FileHandler(filename=log_file)
    rh.setFormatter(formatter)
    rh.setLevel(logging.DEBUG)
    logger.addHandler(rh)

    migrations = {
        '12.0': {
            'branch': '12.0',
            'addons_paths': [
                'odoo/addons',
                'addons',
            ],
            'cmd': [
                './odoo-bin',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc'
            ],
        },
        '11.0': {
            'branch': '11.0',
            'addons_paths': [
                'odoo/addons',
                'addons',
            ],
            'cmd': [
                './odoo-bin',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc'
            ],
        },
        '10.0': {
            'branch': '10.0',
            'addons_paths': [
                'odoo/addons',
                'addons',
            ],
            'cmd': [
                './odoo-bin',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc',
            ],
        },
        '9.0': {
            'branch': '9.0',
            'addons_paths': [
                'openerp/addons',
                'addons',
            ],
            'cmd': [
                './openerp-server',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc',
            ],
        },
        '8.0': {
            'branch': '8.0',
            'addons_paths': [
                'openerp/addons',
                'addons',
            ],
            'cmd': [
                './openerp-server',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc',
            ],
        },
        '7.0': {
            'branch': '7.0',
            'addons_paths': [
                'openerp/addons',
                'addons',
            ],
            'cmd': [
                './openerp-server',
                '--update={module}',
                '--database={db}',
                '--config={configfile}',
                '--stop-after-init',
                '--no-xmlrpc',
                '--no-netrpc',
            ]
        },
    }

    if from_version not in migrations:
        click.echo("Invalid from version: {}".format(from_version))

    for version in sorted(filter(lambda v: float(v) > float(from_version) and float(v) <= float(to_version), migrations), key=lambda x: float(x)):
        (dirs['customs'] / '.version').write_text(version)
        logger.info("""\n========================================================================
Migration to Version {}
========================================================================""".format(version)
                    )

        if module == 'all':
            Commands.invoke(ctx, 'compose', customs=config.customs)
            Commands.invoke(ctx, 'build', machines=['odoo'])
        Commands.invoke(ctx, 'wait_for_container_postgres')

        __run_before_after('before', version, debug, module, logger)
        __run_migration(migrations, git_clean, version, debug, module, logger, pull_latest)
        __run_before_after('after', version, debug, module, logger)
        # __check_for_dangling_modules()

        if not no_auto_backup:
            click.echo("Backup of database Version {}".format(version))
            Commands.invoke(ctx, 'backup_db', filename="{dbname}_{version}".format(version=version, dbname=config.dbname))

    (dirs['customs'] / '.version').write_text(to_version)

    os.unlink(SETTINGS_D_FILE)
    Commands.invoke(ctx, 'build')
    click.echo("Migration process finished - reached end without external exception.")

@cli.command()
@click.argument('from-version', required=True)
@click.argument('to-version', required=True)
@click.option('--module', help="At debugging: to update only the provided module", default='all')
@click.option("-d", "--debug", is_flag=True, help="Interactive mode: stops at breakpoints", default=False)
@click.option("-p", "--pull", is_flag=True, help="Pulls odoo repository before to get latest odoo, otherwise SHA from previous runs are used.", default=False)
@click.option('-n', '--no-git-clean', is_flag=True, help="If true, then the git repo is not touch and you can set break points.")
@click.option('--no-auto-backup', is_flag=True, help="No dumps")
@pass_config
@click.pass_context
def migrate(ctx, config, from_version, to_version, no_git_clean, debug, module, pull, no_auto_backup):
    """
    For debugging migration of certain module provide module parameter.
    """
    from . import odoo_config
    assert float(to_version) >= float(from_version)
    Commands.invoke(ctx, 'kill', machines=["proxy", "odoo"], brutal=True)
    Commands.invoke(ctx, 'kill', brutal=True)
    git_clean = not no_git_clean
    del no_git_clean
    LOGFILE = odoo_config.customs_dir() / "migration_{}_{}.log".format(config.customs, datetime.now().strftime("%Y-%m-%dT%H%M%S"))
    Commands.invoke(ctx, 'fix_permissions')
    try:
        _migrate(
            ctx,
            config,
            LOGFILE,
            from_version,
            to_version,
            SETTINGS_D_FILE=str(dirs['settings.d'] / 'migration'),
            git_clean=git_clean,
            debug=debug,
            module=module,
            pull_latest=pull,
            no_auto_backup=no_auto_backup
        )

    except Exception:
        msg = traceback.format_exc()
        with open(LOGFILE, 'a') as f:
            f.write("\n")
            f.write(msg)
        click.echo(msg)
        click.echo("Error occurred during migration, suggestions:")
        click.echo("")
        click.echo("1. Run odoo version and startup frontend, use ./odoo checkout-odoo -f -v xx.xx to set odoo")
    else:
        click.echo("Running migration after processes (basically module update)")
        Commands.invoke(ctx, 'migrate_run_after_processes', to_version=to_version)

    finally:
        click.echo("To debug an intermediate version, run:")
        click.echo("=====================================")
        click.echo("./odoo unlink [to remove links folder of modules]")
        click.echo("./odoo odoo-module remove-old")
        click.echo("./odoo update --no-update-module-list -m base")
        click.echo("./odoo checkout-odoo -f -v xx.xx")
        click.echo("./odoo dev")

@cli.command(name="migrate-run-after-processes")
@click.argument('to-version', required=True)
@pass_config
@click.pass_context
def migrate_run_after_processes(ctx, config, to_version):
    click.echo("\n\n\nMIGRATION FINAL STEP: Removing old modules\n\n\n")
    Commands.invoke(ctx, 'remove_old_modules', ask_confirm=False)
    click.echo("\n\n\nMIGRATION UPDATE MODULES ROUND1\n\n\n")
    Commands.invoke(ctx, 'update', module=[], dangling_modules=True, installed_modules=True, no_dangling_check=True, check_install_state=False, no_restart=True, non_interactive=True)
    click.echo("\n\n\nMIGRATION UPDATE MODULES ROUND2\n\n\n")
    Commands.invoke(ctx, 'update', module=['base'], check_install_state=False, no_restart=True, no_dangling_check=True, non_interactive=True)
    click.echo("\n\n\nMIGRATION UPDATE MODULES ROUND3\n\n\n")
    Commands.invoke(ctx, 'update', module=[], no_restart=True, no_dangling_check=True, i18n=True, non_interactive=True)
    click.echo("\n\n\nMIGRATION UPDATE MODULES: showing install state\n\n\n")
    Commands.invoke(ctx, 'show_install_state', suppress_error=True)
    click.echo("\n\n\nMIGRATION FINAL STEP: Removing old modules\n\n\n")
    Commands.invoke(ctx, 'remove_old_modules', ask_confirm=False)
    click.echo("\n\n\nMIGRATION FINAL STEP: Backup of final db\n\n\n")
    click.echo("Backup of database Version {}".format(to_version))
    Commands.invoke(ctx, 'backup_db', filename="{dbname}_{version}_final".format(version=to_version, dbname=config.dbname))


Commands.register(migrate_run_after_processes)
