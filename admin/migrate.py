"""

Migration Script


"""
import os
import sys
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


def do_migrate(log_file, from_version, to_version, do_command, SETTINGS_D_FILE, no_auto_backup=False):
    from_version = str(float(from_version))
    to_version = str(float(to_version))

    # Make sure that RUN_MIGRATION is temporarily set to 1
    settings = MyConfigParser(SETTINGS_D_FILE)
    settings.clear()
    settings['RUN_MIGRATION'] = '1'
    settings.write()

    FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s\n%(message)s'
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
            'cmd': './odoo-bin --update=all --database={db} '
                   '--config={configfile} --stop-after-init --no-xmlrpc',
        },
        '10.0': {
            'branch': '10.0',
            'addons_paths': [
                'odoo/addons',
                'addons',
            ],
            'cmd': './odoo-bin --update=all --database={db} '
                   '--config={configfile} --stop-after-init --no-xmlrpc',
        },
        '9.0': {
            'branch': '9.0',
            'addons_paths': [
                'openerp/addons',
                'addons',
            ],
            'cmd': './openerp-server --update=all --database={db} '
                   '--config={configfile} --stop-after-init --no-xmlrpc',
        },
        '8.0': {
            'branch': '8.0',
            'addons_paths': [
                'openerp/addons',
                'addons',
            ],
            'cmd': './openerp-server --update=all --database={db} '
                   '--config={configfile} --stop-after-init --no-xmlrpc',
        },
        '7.0': {
            'branch': '7.0',
            'cmd': './openerp-server --update=all --database={db} '
                   '--config={configfile} --stop-after-init --no-xmlrpc '
                   '--no-netrpc',
        },
    }

    if from_version not in migrations:
        print "Invalid from version: {}".format(from_version)

    def run_cmd(cmd, cwd=None):
        logger.info("Executing:\n{}".format(" ".join(cmd)))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, cwd=cwd)

        def reader(pipe, q):
            try:
                with pipe:
                    for line in iter(pipe.readline, ''):
                        q.put((pipe, line))
            finally:
                q.put(None)

        q = Queue()
        Thread(target=reader, args=[proc.stdout, q]).start()
        Thread(target=reader, args=[proc.stderr, q]).start()
        for source, line in iter(q.get, None):
            line = (line or '').strip()
            if source == proc.stderr:
                logger.error(line)
            else:
                logger.info(line)

        proc.wait()
        if proc.returncode:
            raise Exception("Error executing command, out put is above; command is:\n{}".format(" ".join(cmd)))

    for version in sorted(filter(lambda v: float(v) > float(from_version) and float(v) <= float(to_version), migrations), key=lambda x: float(x)):
        with open(os.path.join(customs_dir(), '.version'), 'w') as f:
            f.write(version)
        logger.info("""\n========================================================================
    Migration to Version {}
    ========================================================================""".format(version)
                    )

        # do_command('build')
        # # make sure postgres is available
        # do_command("wait_for_container_postgres")
        # do_command('run', [
            # "odoo",
            # "/run_migration.sh",
            # 'before',
        # ])
        do_command('run', [
            "odoo",
            "/bin/bash",
            "/opt/migrate.sh",
            migrations[version]['branch'],
            migrations[version]['cmd'].format(configfile=CONFIG_FILE, db=os.environ['DBNAME']),
            ','.join(os.path.join(BASE_PATH, x) for x in migrations[version]['addons_paths']),
        ])
        do_command('run', [
            "odoo",
            "/run_migration.sh",
            'after',
        ])

        if not no_auto_backup:
            do_command('backup-db', [
                "{dbname}_{version}".format(version=version, dbname=os.environ['DBNAME'])
            ])

    with open(os.path.join(customs_dir(), '.version'), 'w') as f:
        f.write(to_version)

    os.unlink(SETTINGS_D_FILE)
    do_command('build')
