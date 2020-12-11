#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path

owner = os.environ['OWNER_UID']
ODOO_SERVER_TOOLS_MODULES = os.environ['ODOO_SERVER_TOOLS_MODULES']

os.system(f"usermod -u {owner} odoo")

print(f"Setting ownership of /opt/files to {owner}")
os.system(f"chown '{owner}:{owner}' /opt/files")
os.system(f"rsync /tmp/odoo_server_tools.template/ {ODOO_SERVER_TOOLS_MODULES} -ar")
os.system("python3 /odoolib/put_server_modules_into_odoo_src_dir.py")

os.system(f"chown '{owner}:{owner}' -R {ODOO_SERVER_TOOLS_MODULES}")
# important is especially the .config folder, so that libreoffice works
print(f"Setting ownership of /home/odoo to {owner}")
os.system(f"chown -R '{owner}:{owner}' /home/odoo")

os.execvp(sys.argv[1], sys.argv[1:])
