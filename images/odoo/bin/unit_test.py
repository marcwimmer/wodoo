#!/usr/bin/python3
import os
import sys
import subprocess
from odoo_tools.module_tools import Module
from odoo_tools.odoo_config import customs_dir
from odoo_tools.odoo_config import current_version
from pathlib import Path
from tools import exec_odoo
from tools import prepare_run

os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'
os.environ["PYTHONBREAKPOINT"] = "pudb.set_trace"

if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)
prepare_run()

filepath = Path(sys.argv[1])
module = Module(filepath)

# make path relative to links, so that test is recognized by odoo
path = filepath.resolve().absolute()
cmd = [
    '--stop-after-init',
    '--test-file={}'.format(path),
]
if current_version() <= 11.0:
    cmd += [
        '--test-report-directory=/tmp',
    ]
exec_odoo(
    "config_unittest",
    *cmd
)
