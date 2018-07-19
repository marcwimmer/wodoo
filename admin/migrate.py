"""

Migration Script

For Debugging OCA Migration script walk into /repos/Openupgrade and edit code.
Provide parameter --no-git-clean then, otherwise traces/changes are removed.


"""
import pipes
import time
import os
import sys
import psycopg2
import pickle
import base64
import logging
import subprocess
from threading import Thread
from Queue import Queue
from logging import FileHandler
from optparse import OptionParser
from module_tools.odoo_config import customs_dir
from module_tools.myconfigparser import MyConfigParser

CONFIG_FILE = '/home/odoo/config_migration'

parser = OptionParser(
    description="""Migration from odoo x to odoo y

-log is written to stdout and parallel to $CUSTOMS_FOLDER/migration.log
-put a migration folder into your customs with following structure:

(These files are optional)
data/src/customs/<customs>/migration/8.0/before.sql
data/src/customs/<customs>/migration/8.0/after.sql
data/src/customs/<customs>/migration/8.0/before.py
data/src/customs/<customs>/migration/8.0/after.py

The py files must contain:

def run(cr):
    ....


"""
)

BASE_PATH = "/opt/odoo_home/repos/OpenUpgrade/" # must match in container

def prepareCommand(cmd, module):
    def repl(s):
        s = s.format(
            configfile=CONFIG_FILE,
            db=os.environ['DBNAME'],
            module=module,
        )
        return s
    cmd = [repl(x) for x in cmd]
    cmd = pickle.dumps(cmd)
    cmd = base64.b64encode(cmd)
    return cmd

def connect_db():
    return psycopg2.connect(
        dbname=os.environ['DBNAME'],
        user=os.environ['DB_USER'],
        host=os.environ['DB_HOST'],
        port=long(os.environ['DB_PORT']),
        password=os.environ['DB_PWD'],
    )

def __check_for_dangling_modules(do_command):
    conn = connect_db()
    cr = conn.cursor()
    cr.execute("select count(*) from ir_module_module where state like 'to install'")  # to upgrade seems to be ok
    if cr.fetchone()[0]:
        do_command('progress')
        raise Exception("Found dangling modules!")
    conn.close()

def __run_before_after(type, version, debug, module, do_command, logger):
    print("Running {} processes {}".format(type, version))
    cmd = [
        "odoo",
        "/usr/bin/python",
        "/run_migration.py",
        type,
    ]
    if module == 'all' and not debug:
        cmd.insert(0, 'run')
        do_command(*tuple(cmd), logger=logger)
    elif debug:
        answer = raw_input("Run before sql/py? [Y/n]")
        if not answer or answer in ['Y', 'y']:
            cmd.insert(0, 'runbash')
            do_command(*tuple(cmd))

def __run_migration(migrations, git_clean, version, debug, module, do_command, logger, pull_latest):
    print("Starting Openupgrade Migration to {}".format(version))
    cmd = [
        'run or runbash see below',
        "odoo",
        "/usr/bin/python",
        "/opt/migrate.sh",
        migrations[version]['branch'],
        prepareCommand(migrations[version]['cmd'], module=module),
        ','.join(os.path.join(BASE_PATH, x) for x in migrations[version]['addons_paths']),
        version,
        '1' if git_clean else '0',
        '1' if pull_latest else '0',
    ]
    if debug:
        cmd[0] = 'runbash'
        do_command(*cmd)
    else:
        cmd[0] = 'run'
        do_command(*cmd, logger=logger, interactive=False)

def do_migrate(customs, log_file, from_version, to_version, do_command, SETTINGS_D_FILE, no_auto_backup=False, git_clean=True, debug=False, module='all', pull_latest=False):
    """

    :param pull_latest: if true, then git pull is done in OpenUpgrade

    """
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

    if os.path.exists(log_file):
        os.unlink(log_file)
    rh = FileHandler(filename=log_file)
    rh.setFormatter(formatter)
    rh.setLevel(logging.DEBUG)
    logger.addHandler(rh)

    migrations = {
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
        print "Invalid from version: {}".format(from_version)

    for version in sorted(filter(lambda v: float(v) > float(from_version) and float(v) <= float(to_version), migrations), key=lambda x: float(x)):
        with open(os.path.join(customs_dir(), '.version'), 'w') as f:
            f.write(version)
        logger.info("""\n========================================================================
Migration to Version {}
========================================================================""".format(version)
                    )

        if module == 'all':
            do_command('compose', customs)
            do_command('build', 'odoo')
        do_command("wait_for_container_postgres")

        __run_before_after('before', version, debug, module, do_command, logger)
        __run_migration(migrations, git_clean, version, debug, module, do_command, logger, pull_latest)
        __run_before_after('after', version, debug, module, do_command, logger)
        __check_for_dangling_modules(do_command)

        if not no_auto_backup:
            print "Backup of database Version {}".format(version)
            do_command(
                'backup-db',
                "{dbname}_{version}".format(version=version, dbname=os.environ['DBNAME'])
            )

    with open(os.path.join(customs_dir(), '.version'), 'w') as f:
        f.write(to_version)

    os.unlink(SETTINGS_D_FILE)
    do_command('build')
    print("Migration process finished - reached end without external exception.")
