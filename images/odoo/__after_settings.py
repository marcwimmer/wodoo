import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    from odoo_tools import odoo_config
    if "CUSTOMS" in config.keys():
        config['ODOO_VERSION'] = str(odoo_config.current_version())
        config.write()
