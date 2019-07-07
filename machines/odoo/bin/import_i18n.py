#!/usr/bin/python3
import shutil
import tempfile
import os
import sys
import subprocess
from module_tools.module_tools import Module
from filepath import Path
if len(sys.argv) == 1:
    print("Usage: import_i18n de_DE pofilepath")
    sys.exit(-1)
if len(sys.argv) == 2:
    print("Language Code and/or Path missing!")
    print("")
    print("Please provide the path relative to customs e.g. modules/mod1/i18n/de.po")
    sys.exit(-1)

LANG = sys.argv[1]
FILEPATH = sys.argv[2]

print( "Importing lang file $FILEPATH")

cmd = [
    "/usr/bin/sudo",
    "-E",
    "-H",
    "-u",
    os.environ['ODOO_USER'],
    os.path.join(os.environ['SERVER_DIR'], os.environ['ODOO_EXECUTABLE']),
    '-d', os.environ['DBNAME'],
    '-c', os.path.join(os.environ['CONFIG_DIR'], 'config_i18n'),
    '--pidfile={}'.format(os.environ['DEBUGGER_ODOO_PID']),
    '--stop-after-init',
    '--log-level=warn',
    '-l', LANG,
    '--i18n-import={}'.format(filename),
    '--i18n-overwrite',
]
subprocess.call(cmd)
