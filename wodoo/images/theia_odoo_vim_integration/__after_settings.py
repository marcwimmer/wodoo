
import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    from wodoo import odoo_config

    # disable theia on live system
    if config['DEVMODE'] != "1":
        config['RUN_THEIA_ODOO_VIM'] = '0'
        config['RUN_THEIA_ODOO_VIM_INTEGRATION'] = '0'