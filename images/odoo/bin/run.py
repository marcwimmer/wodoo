#!/usr/bin/env python3
import os
import subprocess
import tools
from tools import prepare_run
from tools import exec_odoo
from tools import is_odoo_cronjob
from tools import is_odoo_queuejob
print("Starting up odoo")
prepare_run()

touch_url = not is_odoo_cronjob and not is_odoo_queuejob

exec_odoo(None, '--log-level={}'.format(os.environ["ODOO_LOG_LEVEL"]), touch_url=touch_url)
