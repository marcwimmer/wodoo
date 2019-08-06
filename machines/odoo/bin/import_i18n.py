#!/usr/bin/python3
import shutil
import tempfile
import os
import sys
import subprocess
from module_tools.module_tools import Module
from pathlib import Path
from tools import exec_odoo
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

print("Importing lang file $FILEPATH")

exec_odoo(
    'config_i18n',
    '--stop-after-init',
    '--log-level=warn',
    '-l', LANG,
    '--i18n-import={}'.format(FILEPATH),
    '--i18n-overwrite',
)
