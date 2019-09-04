import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):
    from pudb import set_trace
    set_trace()
    if config.run_btrfs:
        config['RUN_POSTGRES_IN_BTRFS'] = '1'
        config.write()
