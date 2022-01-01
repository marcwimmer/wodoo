import stat
import os
import platform
import subprocess
from pathlib import Path
import inspect

def after_settings(config):
    from wodoo import odoo_config

    m = odoo_config.MANIFEST()

    config['SERVER_WIDE_MODULES'] = ','.join(m['server-wide-modules'])

    # if odoo does not exist yet and version is given then we setup gimera and clone it 

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

        config['ODOO_QUEUEJOBS_WORKERS'] = str(int(Sum * 2)) # good for all in one also
        config['ODOO_QUEUEJOBS_CHANNELS'] = channels

    if config['LOCAL_SETTINGS'] == '1':
        config['ODOO_FILES'] = str(Path(config['HOST_RUN_DIR']) / 'files')
