#!/usr/bin/env python3
import os
from pathlib import Path
from tools import exec_odoo
import sys

ENV = {
}

if float(os.environ['ODOO_VERSION']) <= 7.0:
    DEV = ""
elif float(os.environ['ODOO_VERSION']) <= 9.0:
    DEV = '--dev'
else:
    DEV = '--dev=pudb,qweb,xml,werkzeug'

exec_odoo(
    'config_debug',
    DEV,
    env=ENV,
    remote_debug='--remote-debug' in sys.argv,
    wait_for_remote='--wait-for-remote' in sys.argv,
)
