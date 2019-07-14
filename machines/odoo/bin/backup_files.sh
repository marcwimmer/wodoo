#!/usr/bin/env python3 
import subprocess
from module_tools import odoo_config
DESTFILE = "/opt/dumps/{}".format(odoo_config.current_customs())

subprocess.check_call([
    "/bin/tar",
    "cfz",
    DESTFILE,
    "/opt/files"
])
