#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path

passwd = Path("/etc/passwd")
content = passwd.read_text()
content = content.replace("1000:1000", "{uid}:{uid}".format(uid=os.environ['OWNER_UID']))
passwd.write_text(content)

config_dir = Path(os.environ['ODOO_CONFIG_DIR'])
config_dir_template = Path(os.environ['ODOO_CONFIG_DIR'] + '.template')
if not list(config_dir.glob("*")):
    config_dir.mkdir(exist_ok=True, parents=True)
    for file in config_dir_template.glob("*"):
        shutil.copy(str(file), str(config_dir / file.name))

os.execvp(sys.argv[1], sys.argv[1:])
