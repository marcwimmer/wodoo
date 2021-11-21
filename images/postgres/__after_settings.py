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
            if not config.get(k, ""):
                config[k] = v