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

        file = Path(f"/tmp/odoo-compose/{config['PROJECT_NAME']}.postgres_port")
        if not file.exists():
            port = random.randint(10001, 30000)
            file.parent.mkdir(exist_ok=True, parents=True)
            file.write_text(str(port))

        if not config.get("POSTGRES_PORT", ""):
            # try to use same port again
            config['POSTGRES_PORT'] = int(file.read_text().strip())
