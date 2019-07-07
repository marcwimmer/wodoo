#!/usr/bin/python3
import os
import sys
import subprocess
from module_tools.module_tools import Module
from pathlib import Path
if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)

subprocess.check_call(['reset'])

filepath = Path(sys.argv[1])
module = Module(filepath)
path = module.path / 'tests' / filepath.name

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
    '--test-report-directory=/tmp',
    '--log-level=debug',
]
subprocess.call(cmd)
