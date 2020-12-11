#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path
from odoo_tools.odoo_config import customs_dir

owner = os.environ['OWNER_UID']
ODOO_SERVER_TOOLS_MODULES = os.environ['ODOO_SERVER_TOOLS_MODULES']

# also update the source in addons_tools, so that developers without using this framework
# have the modules in a sub path
for tool_module_dir in Path("/tmp/odoo_server_tools.template").glob("*"):
    if tool_module_dir.is_dir():
        dest_path = f'{customs_dir()}/addons_tools/{tool_module_dir.name}'
        os.system(f"rsync {tool_module_dir}/ {dest_path}/  -ar --delete-after")
        os.system(f"chown -R {owner}:{owner} '{dest_path}' ")
