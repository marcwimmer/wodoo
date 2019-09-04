#!/usr/bin/env python3
from pathlib import Path
from tools import exec_odoo

ENV = {
    "TEST_QUEUE_JOB_NO_DELAY": "1", # for module queue_job
    "ODOO_TRACE": "1"
}
exec_odoo(
    'config_debug',
    env=ENV
)
