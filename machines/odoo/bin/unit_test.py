#!/usr/bin/python3
import os
import sys
import subprocess
from module_tools.module_tools import get_module_of_file
if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)

subprocess.check_call(['reset'])

filepath = sys.argv[1]
module = get_module_of_file(filepath)
path = os.path.join(
    os.environ['ADDONS_CUSTOMS'],
    module,
    'tests',
    os.path.basename(filepath)
)

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
