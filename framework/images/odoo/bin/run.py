#!/usr/bin/env python3
import os
from tools import prepare_run
from tools import exec_odoo
from tools import is_odoo_cronjob
from tools import is_odoo_queuejob
print("Starting up odoo")
prepare_run()

TOUCH_URL = not is_odoo_cronjob and not is_odoo_queuejob

exec_odoo(
    None,
    '--log-level={}'.format(
        os.getenv("ODOO_LOG_LEVEL", "debug")
    ),
    touch_url=TOUCH_URL,
)
