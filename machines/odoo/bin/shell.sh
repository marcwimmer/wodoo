#!/usr/bin/env python3
import sys
import os
import subprocess
from module_tools import odoo_config
import consts
import tools
from consts import ODOO_USER
from tools import prepare_run
from tools import get_config_file
config = odoo_config.get_env()

prepare_run()

    OPTIONS=""
if odoo_config.current_version() >= 11.0:
    options = "--shell-interface=ipython"
     shell -d $DBNAME -c $CONFIG_DIR/config_shell $OPTIONS

subprocess.check_call([
    "/usr/bin/sudo",
    "-E",
    "-H",
    "-u",
    ODOO_USER,
    EXEC,
    GEVENT_MARKER,
    '-c',
    get_config_file(CONFIG),
    '-d',
    config['DBNAME'],
    '--log-level={}'.format(os.environ["ODOO_LOG_LEVEL"])
])
