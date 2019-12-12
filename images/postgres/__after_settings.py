import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
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

    if "RUN_POSTGRES" in config.keys() and config.get("RUN_POSTGRES", "") != "1" and config.get("RUN_POSTGRES_IN_RAM", "") == "1":
        config['RUN_POSTGRES_IN_RAM'] = "1"

    if config.get('RUN_BTRFS', "") == "1":
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()
    else:
        config['RUN_POSTGRES_IN_BTRFS'] = '0'

    customs = config['CUSTOMS']
    dbname = config['DBNAME']
    project_name = os.environ['PROJECT_NAME']
    if config['DEVMODE'] != '1':
        config['POSTGRES_VOLUME_NAME'] = "{}_postgres".format(project_name)
    else:
        config['POSTGRES_VOLUME_NAME'] = "{}_{}_postgres".format(customs, dbname)
