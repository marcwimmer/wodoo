#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path

os.system("usermod -u {} odoo".format(os.environ['OWNER_UID']))

print("Setting ownership of /opt/files to {}".format(os.environ['OWNER_UID']))
os.system("chown '{owner}:{owner}' /opt/files".format(owner=os.environ['OWNER_UID']))
# important is especially the .config folder, so that libreoffice works
print("Setting ownership of /home/odoo to {}".format(os.environ['OWNER_UID']))
os.system("chown '{owner}:{owner}' /home/odoo -R ".format(owner=os.environ['OWNER_UID']))

os.execvp(sys.argv[1], sys.argv[1:])
