#!/usr/bin/env python3
import os
from pathlib import Path
from tools import exec_odoo

ENV = {
    "TEST_QUEUE_JOB_NO_DELAY": "1", # for module queue_job
    "ODOO_TRACE": "1"
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
)
