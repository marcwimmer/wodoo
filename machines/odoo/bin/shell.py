#!/usr/bin/python3
import os
import sys
import subprocess
from module_tools.module_tools import Module
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import current_version
from pathlib import Path
from tools import exec_odoo
from tools import prepare_run

prepare_run()

subprocess.check_call(['reset'])

# make path relative to links, so that test is recognized by odoo
cmd = [
    '--log-level=debug',
    '--stop-after-init',
]
if current_version() >= 11.0:
    cmd += ["--shell-interface=ipython"]
exec_odoo(
    "config_shell",
    *cmd,
    odoo_shell=True
)
