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

    # replace any env variable
    if config.get("ODOO_QUEUEJOBS_CHANNELS", ""):
        channels = [(x, int(y)) for x, y in list(map(lambda x: x.strip().split(':'), [X for X in config['ODOO_QUEUEJOBS_CHANNELS'].split(",")]))]
        channels_no_root = [x for x in channels if x[0] != 'root']
        if channels_no_root:
            Sum = sum(x[1] for x in channels_no_root)
        elif channels:
            Sum = sum(x[1] for x in channels)
        else:
            raise Exception("Please define at least on root channel for odoo queue jobs.")

        channels = ','.join(f"{x[0]}:{x[1]}" for x in [('root', Sum)] + channels_no_root)

        config['ODOO_QUEUEJOBS_WORKERS'] = str(Sum)
        config['ODOO_QUEUEJOBS_CHANNELS'] = channels

