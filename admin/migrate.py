"""

Migration Script


"""
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

def prepareCommand(cmd):
    def repl(s):
        s = s.format(
            configfile=CONFIG_FILE,
            db=os.environ['DBNAME'])
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


def do_migrate(customs, log_file, from_version, to_version, do_command, SETTINGS_D_FILE, no_auto_backup=False):
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
                '--update=all',
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
                '--update=all',
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
                '--update=all',
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
                '--update=all',
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
                '--update=all',
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

        do_command('compose', customs)
        do_command('build')
        do_command("wait_for_container_postgres")
        do_command(
            'run',
            "odoo",
            "/run_migration.sh",
            'before',
            logger=logger,
        )
        print("Starting Openupgrade Migration to {}".format(version))
        do_command(
            'run',
            "odoo",
            "/usr/bin/python",
            "/opt/migrate.sh",
            migrations[version]['branch'],
            prepareCommand(migrations[version]['cmd']),
            ','.join(os.path.join(BASE_PATH, x) for x in migrations[version]['addons_paths']),
            version,
            logger=logger,
        )
        print("Running after processes {}".format(version))
        do_command(
            'run',
            "odoo",
            "/run_migration.sh",
            'after',
            logger=logger,
        )
        conn = connect_db()
        cr = conn.cursor()
        cr.execute("select count(*) from ir_module_module where state like 'to %'")
        if cr.fetchone()[0]:
            do_command('progress')
            raise Exception("Found dangling modules!")
        conn.close()

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
