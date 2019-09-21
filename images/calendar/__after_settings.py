import stat
import os
import platform
from pathlib import Path
import inspect

def after_settings(config):

    if "RUN_CALENDAR" in config.keys() and config.get("RUN_CALENDAR", "") == "1":
        config['RUN_CALENDAR_DB'] = "1"
