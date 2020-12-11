import random
import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    if config.get("USE_DOCKER", "1") == "0":
        config['RUN_POSTGRES'] = '0'
    if 'RUN_POSTGRES' in config.keys() and config['RUN_POSTGRES'] == '1':
        default_values = {
            "DB_HOST": "postgres",
            "DB_PORT": "5432",
            "DB_USER": "odoo",
            "DB_PWD": "odoo"
        }
        for k, v in default_values.items():
            if config.get(k, "") != v:
                config[k] = v

        if not config.get("POSTGRES_PORT", ""):
            # try to use same port again
            port = random.randint(10001, 30000)
            config['POSTGRES_PORT'] = str(port)

    if config.get('RUN_BTRFS', "") == "1":
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()
    else:
        config['RUN_POSTGRES_IN_BTRFS'] = '0'

    customs = config['CUSTOMS']
    dbname = config['DBNAME']
    project_name = config['PROJECT_NAME']
    if config['DEVMODE'] != '1':
        config['POSTGRES_VOLUME_NAME'] = "{}_postgres".format(project_name)
    else:
        config['POSTGRES_VOLUME_NAME'] = "{}_{}_{}_postgres".format(
            os.environ['USER'],
            customs,
            dbname
        )
