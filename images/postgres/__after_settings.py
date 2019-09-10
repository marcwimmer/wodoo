import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    import pudb
    pudb.set_trace()
    if config.get('RUN_BTRFS', ""):
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()

    customs = config['CUSTOMS']
    dbname = config['DBNAME']
    project_name = os.environ['PROJECT_NAME']
    if config['DEVMODE'] != '1':
        config['POSTGRES_VOLUME_NAME'] = "{}_postgres".format(project_name)
    else:
        config['POSTGRES_VOLUME_NAME'] = "{}_{}_postgres".format(customs, dbname)
