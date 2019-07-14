from pudb import set_trace
set_trace()
import os

import subprocess
from pathlib import Path

from . import consts
from module_tools import odoo_config
from .tools import run_autosetup
from .tools import replace_variables_in_config_files

from . import run # NOQA
from . import shell # NOQA
from . import unit_test # NOQA
from . import update_modules # NOQA
