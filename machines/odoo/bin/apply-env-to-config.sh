#!/usr/bin/python
import os

if not os.getenv("DB_HOST") or not os.getenv("DB_USER"):
    raise Exception("Please define all DB Env Variables!")

import sys
sys.path.append(os.path.join(os.environ['ADMIN_DIR'], 'module_tools'))
import odoo_config
ADDONS_PATHS = ','.join(filter(lambda t: t, odoo_config.get_odoo_addons_paths() + [os.getenv('ADDONS_CUSTOMS')] + [os.getenv("ADDONS_PATHS")]))

for file in os.listdir("/home/odoo"):
    if file.startswith("config_"):
        filepath = os.path.join('/home/odoo', file)
        with open(filepath, 'r') as f:
            content = f.read()

        content = content.replace("__ADDONS_PATH__", ADDONS_PATHS)

        if 'without_demo=' not in content:
            if os.getenv("ODOO_DEMO", "") == "1":
                content = content + "\nwithout_demo=False"
            else:
                content = content + "\nwithout_demo=all"

        for key in [
            "DB_USER", "DB_PWD", "DB_MAXCONN",
            "DB_PORT", "DB_HOST", "ODOO_MAX_CRON_THREADS"
        ]:
            content = content.replace("__{}__".format(key), os.getenv(key, ""))

        with open(filepath, 'w') as f:
            f.write(content)
