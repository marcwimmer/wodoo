import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    if config.get('RUN_BTRFS', ""):
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()

    customs = config['CUSTOMS']
    dbname = config['DBNAME']
    config['POSTGRES_VOLUME_NAME'] = "{}_{}_postgres".format(customs, dbname)
