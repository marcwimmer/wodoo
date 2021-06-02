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
    os.getenv("")
    # eg: pudb.set_trace
    # not really supported by odoo yet; they call post mortem function
    # import pudb;pudb.set_trace()kj
    # PYBREAKPOINT = os.getenv("PYTHONBREAKPOINT", "pudb").split(".")[0]
    PYBREAKPOINT = 'pudb'
    DEV = f'--dev={PYBREAKPOINT},qweb,xml,werkzeug'

exec_odoo(
    'config_debug',
    DEV,
    env=ENV,
    remote_debug='--remote-debug' in sys.argv,
    wait_for_remote='--wait-for-remote' in sys.argv,
)
