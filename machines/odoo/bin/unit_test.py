#!/usr/bin/python3
import os
import sys
import subprocess
from module_tools.module_tools import Module
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import current_version
from pathlib import Path
from tools import exec_odoo
from tools import prepare_run

if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)
prepare_run()

subprocess.check_call(['reset'])
filepath = Path(sys.argv[1])
module = Module(filepath)

# make path relative to links, so that test is recognized by odoo
#path = customs_dir() / 'links' / module.name / filepath.resolve().relative_to(module.path)
path = filepath.resolve().absolute()
cmd = [
    '--stop-after-init',
    '--test-file={}'.format(path),
    '--log-level=debug',
]
if current_version() <= 11.0:
    cmd += [
        '--test-report-directory=/tmp',
    ]
exec_odoo(
    "config_unittest",
    *cmd,
)
