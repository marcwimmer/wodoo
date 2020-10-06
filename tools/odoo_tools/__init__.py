import time
import sys
from datetime import datetime
from pathlib import Path
import imp
import inspect
import os
import glob
# from .myconfigparser import MyConfigParser  # NOQA load this module here, otherwise following lines and sublines get error
from .init_functions import load_dynamic_modules
from .init_functions import _get_customs_root
from .click_config import Config

from .click_global_commands import GlobalCommands
try:
    import click
    from .lib_clickhelpers import AliasedGroup
except ImportError:
    click = None
from .tools import _file2env

dir = Path(inspect.getfile(inspect.currentframe())).resolve().parent
sys.path.append(dir / '..' / 'module_tools')
from . import module_tools # NOQA
from . import odoo_config  # NOQA
SCRIPT_DIRECTORY = Path(inspect.getfile(inspect.currentframe())).absolute().parent

Commands = GlobalCommands()


if click:
    pass_config = click.make_pass_decorator(Config, ensure=True)

    @click.group(cls=AliasedGroup)
    @click.option("-f", "--force", is_flag=True)
    @pass_config
    def cli(config, force):
        config.force = force
        if not config.WORKING_DIR:
            click.secho("Please enter into an odoo directory, which contains a MANIFEST file.", fg='red')
            sys.exit(1)

        # TODO
        # if not HOST_RUN_DIR.exists():
            # with cli.make_context('odoo', ['-f']) as ctx:
                # Commands.invoke(ctx, 'reload')


from . import lib_clickhelpers  # NOQA
from . import lib_composer # NOQA
from . import lib_backup # NOQA
from . import lib_control # NOQA
from . import lib_db # NOQA
from . import lib_db_snapshots # NOQA
from . import lib_lang # NOQA
from . import lib_module # NOQA
from . import lib_patches # NOQA
from . import lib_setup # NOQA
from . import lib_src # NOQA
from . import lib_venv # NOQA
from . import lib_turnintodev # NOQA

# import container specific commands
from .tools import abort # NOQA
from .tools import __dcrun # NOQA
from .tools import __dc # NOQA

load_dynamic_modules((SCRIPT_DIRECTORY / 'images'))
