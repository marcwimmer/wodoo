#!/usr/bin/python3
import shutil
import tempfile
import os
import sys
import subprocess
from module_tools.module_tools import Module
from filepath import Path
if len(sys.argv) == 1:
    print("Usage: export_i18n de_DE [filepath of po file optional]")
    sys.exit(-1)

LANG = sys.argv[1]
MODULES = sys.argv[2]

module = Module.get_by_name(module)
# export_dir="${ADDONS_CUSTOMS}/$MODULES"

path = module.path / 'i18n'
path.mkdir(exist_ok=True0

filename = tempfile.mktemp(suffix='.po')

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
    '--i18n-export={}'.format(filename),
    '--modules={}'.format(module.name),
]
subprocess.call(cmd)

dest_path = module.path / 'i18n' / "{}.po".format(LANG)
filename.rename(dest_path)
odoo_user = os.environ["ODOO_USER"]
owner_group = os.getenv("OWNER_GID", odoo_user)
shutil.chown(dest_path, user=odoo_user, group=odoo_owner_group)
shutil.chown(dest_path.parent, user=odoo_user, group=odoo_owner_group)
