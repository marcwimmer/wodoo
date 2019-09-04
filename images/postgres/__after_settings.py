import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    if config['RUN_BTRFS']:
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()
