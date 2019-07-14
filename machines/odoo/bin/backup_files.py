#!/usr/bin/env python3 
import sys
import subprocess
from pathlib import Path
from module_tools import odoo_config
path = Path(sys.argv[1])
DESTFILE = "/opt/dumps/{}".format(path.name)
d = "/opt/files"

subprocess.check_call([
    "/bin/tar",
    "cfz",
    DESTFILE,
    d,
], cwd=d)
