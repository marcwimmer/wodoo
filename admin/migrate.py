"""

Migration Script


"""
import os
import sys
import logging
import subprocess
from logging import FileHandler
from optparse import OptionParser
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import customs_dir
from module_tools.myconfigparser import MyConfigParser

parser = OptionParser(
    description='Migration from odoo x to odoo y'
    ''
    '-log is written to stdout and parallel to $CUSTOMS_FOLDER/migration.log'
    '-put a migration folder into your customs'
    '-put destination .version into your customs'
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

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(filename="/dev/null", format=FORMAT)
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
        'server': {
            'url': 'git://github.com/OpenUpgrade/OpenUpgrade.git',
            'branch': '11.0',
            'cmd': 'odoo-bin --update=all --database=%(db)s '
                   '--config=%(config)s --stop-after-init --no-xmlrpc',
        },
    },
    '10.0': {
        'server': {
            'url': 'git://github.com/OpenUpgrade/OpenUpgrade.git',
            'branch': '10.0',
            'addons_dir': os.path.join('odoo', 'addons'),
            'root_dir': os.path.join(''),
            'cmd': 'odoo-bin --update=all --database=%(db)s '
                   '--config=%(config)s --stop-after-init --no-xmlrpc',
        },
    },
    '9.0': {
        'server': {
            'url': 'git://github.com/OpenUpgrade/OpenUpgrade.git',
            'branch': '9.0',
            'cmd': 'openerp-server --update=all --database=%(db)s '
                   '--config=%(config)s --stop-after-init --no-xmlrpc',
        },
    },
    '8.0': {
        'server': {
            'url': 'git://github.com/OpenUpgrade/OpenUpgrade.git',
            'branch': '8.0',
            'cmd': 'openerp-server --update=all --database=%(db)s '
                   '--config=%(config)s --stop-after-init --no-xmlrpc',
        },
    },
    '7.0': {
        'server': {
            'url': 'git://github.com/OpenUpgrade/OpenUpgrade.git',
            'branch': '7.0',
            'cmd': 'openerp-server --update=all --database=%(db)s '
                   '--config=%(config)s --stop-after-init --no-xmlrpc '
                   '--no-netrpc',
        },
    },
}

if options.from_version not in migrations:
    print "Invalid from version: {}".format(options.from_version)


for version in sorted(filter(lambda v: float(v) >= float(options.from_version) and float(v) <= float(options.to_version), migrations), key=lambda x: float(x)):
    with open(os.path.join(customs_dir(), '.version'), 'w') as f:
        f.write(version)
    logger.info("""\n========================================================================
Migration to Version {}
========================================================================""".format(version)
                )
    #subprocess.check_call([options.manage_command, "build"])

with open(os.path.join(customs_dir(), '.version'), 'w') as f:
    f.write(options.to_version)
