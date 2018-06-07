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
parser.add_option(
    "-L", "--log-file", action="store", type="string",
    dest="log_file",
    help="log file (required)")
parser.add_option(
    "-F", "--from-version", action="store", type="string",
    dest="from_version",
    help="migrate from version (required)")
parser.add_option(
    "-T", "--to-version", action="store", type="string",
    dest="to_version",
    help="migrate to version (required)")
parser.add_option(
    "-C", "--manage-command", action="store", type="string",
    dest="manage_command",
    help="manage command default /opt/odoo/admin/odoo-admin (required)")
parser.add_option(
    "--no-auto-backup", action="store_true",
    default=False,
    dest="no_auto_backup",
    help="if set, then no backups are done; otherwise after every migration a dump is created; existing dump is overwritten")
(options, args) = parser.parse_args()


if not options.from_version or \
        not options.to_version or \
        not options.manage_command or \
        not options.log_file:
    parser.print_help()
    sys.exit()

# Make sure that RUN_MIGRATION is temporarily set to 1
settings = MyConfigParser("/opt/odoo/run/settings")
settings['RUN_MIGRATION'] = '1'
settings.write()

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s\n%(message)s'
logging.basicConfig(filename="/dev/stdout", format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler
formatter = logging.Formatter(FORMAT)

if os.path.exists(options.log_file):
    os.unlink(options.log_file)
rh = FileHandler(filename=options.log_file)
rh.setFormatter(formatter)
rh.setLevel(logging.DEBUG)
logger.addHandler(rh)

migrations = {
    '11.0': {
        'branch': '11.0',
        'cmd': 'odoo-bin --update=all --database={db} '
               '--config={configfile} --stop-after-init --no-xmlrpc',
    },
    '10.0': {
        'branch': '10.0',
        'cmd': 'odoo-bin --update=all --database={db} '
               '--config={configfile} --stop-after-init --no-xmlrpc',
    },
    '9.0': {
        'branch': '9.0',
        'cmd': 'openerp-server --update=all --database={db} '
               '--config={configfile} --stop-after-init --no-xmlrpc',
    },
    '8.0': {
        'branch': '8.0',
        'cmd': 'openerp-server --update=all --database={db} '
               '--config={configfile} --stop-after-init --no-xmlrpc',
    },
    '7.0': {
        'branch': '7.0',
        'cmd': 'openerp-server --update=all --database={db} '
               '--config={configfile} --stop-after-init --no-xmlrpc '
               '--no-netrpc',
    },
}

if options.from_version not in migrations:
    print "Invalid from version: {}".format(options.from_version)

def run_cmd(cmd):
    logger.info("Executing:\n{}".format(" ".join(cmd)))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)

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


for version in sorted(filter(lambda v: float(v) > float(options.from_version) and float(v) <= float(options.to_version), migrations), key=lambda x: float(x)):
    with open(os.path.join(customs_dir(), '.version'), 'w') as f:
        f.write(version)
    logger.info("""\n========================================================================
Migration to Version {}
========================================================================""".format(version)
                )

    run_cmd([
        options.manage_command,
        "build",
    ])
    run_cmd([
        options.manage_command,
        "run",
        "odoo",
        "/run_migration.sh",
        'before',
    ])

    # run_cmd([
        # options.manage_command,
        # "run",
        # "odoo",
        # "/run_openupgradelib.sh",
        # migrations[version]['branch'],
        # migrations[version]['cmd'].format(configfile=CONFIG_FILE, db=os.environ['DBNAME'])
    # ])

    run_cmd([
        options.manage_command,
        "run",
        "odoo",
        "/run_migration.sh",
        'after',
    ])

    if not options.no_auto_backup:
        run_cmd([
            options.manage_command,
            "backup-db",
            "{dbname}_{version}".format(version=version, dbname=os.environ['DBNAME']),
        ])

with open(os.path.join(customs_dir(), '.version'), 'w') as f:
    f.write(options.to_version)
