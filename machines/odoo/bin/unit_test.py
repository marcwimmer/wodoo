#!/usr/bin/python3
import os
import sys
import subprocess
from module_tools.module_tools import Module
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import get_version_from_customs
from pathlib import Path
if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)

VERSION = get_version_from_customs()
subprocess.check_call(['reset'])

filepath = Path(sys.argv[1])
module = Module(filepath)

# make path relative to links, so that test is recognized by odoo
path = customs_dir() / 'links' / module.name / filepath.resolve().relative_to(module.path)

cmd = [
    "/usr/bin/sudo",
    "-E",
    "-H",
    "-u",
    os.environ['ODOO_USER'],
    os.path.join(os.environ['SERVER_DIR'], os.environ['ODOO_EXECUTABLE']),
    '-d', os.environ['DBNAME'],
    '-c', os.path.join(os.environ['CONFIG_DIR'], 'config_unittest'),
    '--pidfile={}'.format(os.environ['DEBUGGER_ODOO_PID']),
    '--stop-after-init',
    '--test-file={}'.format(path),
    '--log-level=debug',
]
if VERSION <= 11.0:
    cmd += [
        '--test-report-directory=/tmp',
    ]

subprocess.call(cmd)
