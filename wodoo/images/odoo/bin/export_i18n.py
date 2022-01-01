#!/usr/bin/env python3
import shutil
import tempfile
import os
import sys
import grp
import pwd
import subprocess
from wodoo.module_tools import Module
from pathlib import Path
from tools import exec_odoo
if len(sys.argv) == 1:
    print("Usage: export_i18n de_DE module")
    sys.exit(-1)

LANG = sys.argv[1]
MODULES = sys.argv[2]

for module in MODULES.split(","):
    module = Module.get_by_name(MODULES)

    path = module.path / 'i18n'
    path.mkdir(exist_ok=True)

    filename = Path(tempfile.mktemp(suffix='.po'))

    exec_odoo(
        'config_i18n',
        '--stop-after-init',
        '-l', LANG,
        '--i18n-export={}'.format(str(filename)),
        '--modules={}'.format(module.name),
    )

    dest_path = module.path / 'i18n' / "{}.po".format(LANG)
    shutil.copy(str(filename), str(dest_path))
    filename.unlink()
    odoo_user = pwd.getpwnam(os.environ["ODOO_USER"]).pw_uid
    gid = int(os.getenv("OWNER_GID", odoo_user))
    os.chown(str(dest_path), odoo_user, gid)
    os.chown(str(dest_path.parent), odoo_user, gid)
