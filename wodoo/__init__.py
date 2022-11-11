import sys
import subprocess
from datetime import datetime
from pathlib import Path
import inspect
import os

# from .myconfigparser import MyConfigParser  # NOQA load this module here, otherwise following lines and sublines get error
try:
    import click
    from .lib_clickhelpers import AliasedGroup
except ImportError:
    click = None
from .tools import _file2env

from . import module_tools  # NOQA
from . import odoo_config  # NOQA

SCRIPT_DIRECTORY = Path(inspect.getfile(inspect.currentframe())).absolute().parent


os.environ["HOST_HOME"] = os.getenv("HOME", "")
os.environ["ODOO_HOME"] = str(SCRIPT_DIRECTORY)


from .cli import cli
from . import lib_clickhelpers  # NOQA
from . import lib_composer  # NOQA
from . import lib_backup  # NOQA
from . import lib_control  # NOQA
from . import lib_db  # NOQA
from . import lib_db_snapshots  # NOQA
from . import lib_lang  # NOQA
from . import lib_module  # NOQA
from . import lib_setup  # NOQA
from . import lib_src  # NOQA
from . import lib_docker_registry  # NOQA
from . import lib_turnintodev  # NOQA
from . import lib_talk  # NOQA
from . import daddy_cleanup  # NOQA

# import container specific commands
from .tools import abort  # NOQA
from .tools import __dcrun  # NOQA
from .tools import __dc  # NOQA
