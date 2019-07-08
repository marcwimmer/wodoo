#!/usr/bin/python3
# Autosetup searches in /opt/odoo/customs/$CUSTOMS/autosetup for
# *.sh files; makes them executable and executes them
# You can do setup there, like deploying ssh keys and so on
import os
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import get_version_from_customs
from pathlib import Path

if os.getenv("RUN_AUTOSETUP", "") == "1":
    path = customs_dir() / 'autosetup'
    if path.exists():
        for file in path.glob("*.sh"):
            print("executing {}".format(file))
            os.system("bash '{}' {}".format(
                file,
                os.environ['ODOO_AUTOSETUP_PARAM'],
            ), cwd=path)
