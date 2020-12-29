#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path

owner = os.environ['OWNER_UID']

os.system(f"usermod -u {owner} odoo")

print(f"Setting ownership of /opt/files to {owner}")
os.system(f"chown '{owner}:{owner}' /opt/files")
os.system("python3 /odoolib/put_server_modules_into_odoo_src_dir.py")

# important is especially the .config folder, so that libreoffice works
print(f"Setting ownership of /home/odoo to {owner}")
os.system(f"chown -R '{owner}:{owner}' /home/odoo")

os.execvp(sys.argv[1], sys.argv[1:])
