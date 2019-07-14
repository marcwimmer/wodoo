#!/usr/bin/env python3
import os
import subprocess
import tools
from tools import prepare_run
from tools import exec_odoo
print("Starting up odoo")
prepare_run()
exec_odoo(None, '--log-level={}'.format(os.environ["ODOO_LOG_LEVEL"]))
