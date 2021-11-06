import time
import sys
from datetime import datetime
from pathlib import Path
from .click_config import Config
import imp
import inspect
import os
import glob
# from .myconfigparser import MyConfigParser  # NOQA load this module here, otherwise following lines and sublines get error
from .init_functions import load_dynamic_modules
from .init_functions import _get_customs_root

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

os.environ['HOST_HOME'] = os.environ['HOME']
os.environ['ODOO_HOME'] = str(SCRIPT_DIRECTORY.parent.parent)

def _get_default_project_name():
    path = Path(os.path.expanduser("~/.odoo/settings"))
    if path.exists():
        pj = [x for x in path.read_text().split("\n") if 'PROJECT_NAME' in x]
        if pj:
            return pj[0].split("=")[-1].strip()
    root = Path(_get_customs_root(Path(os.getcwd())))
    if (root / "MANIFEST").exists():
        return root.name
    raise Exception("No default project name could be determined.")

if click:
    pass_config = click.make_pass_decorator(Config, ensure=True)

    @click.group(cls=AliasedGroup)
    @click.option("-f", "--force", is_flag=True)
    @click.option("-v", "--verbose", is_flag=True)
    @click.option("-x", '--restrict', multiple=True, help="Several parameters; limit to special configuration files settings and docker-compose files. All other configuration files will be ignored.")
    @click.option("-p", '--project-name', help="Set Project-Name")
    @pass_config
    def cli(config, force, verbose, project_name, restrict):
        config.force = force
        config.verbose = verbose
        if project_name:
            config.project_name = project_name
        else:
            config.project_name = _get_default_project_name()
        if not config.WORKING_DIR:
            # usually all need a working except cicd
            click.secho("Please enter into an odoo directory, which contains a MANIFEST file.", fg='red')
            sys.exit(1)

        config.restrict = []
        if restrict:
            restrict = [Path(x).absolute() for x in restrict]
            for test in restrict:
                if not test.exists():
                    click.secho(f"Not found: {test}", fg='red')
                    sys.exit(-1)
                config.restrict.append(test)
                del test


from . import lib_clickhelpers  # NOQA
from . import lib_composer # NOQA
from . import lib_backup # NOQA
from . import lib_control # NOQA
from . import lib_db # NOQA
from . import lib_db_snapshots # NOQA
from . import lib_lang # NOQA
from . import lib_module # NOQA
from . import lib_setup # NOQA
from . import lib_src # NOQA
from . import lib_docker_registry # NOQA
from . import lib_venv # NOQA
from . import lib_turnintodev # NOQA
# from . import lib_setup # NOQA

# import container specific commands
from .tools import abort # NOQA
from .tools import __dcrun # NOQA
from .tools import __dc # NOQA

load_dynamic_modules((SCRIPT_DIRECTORY / '..' / '..' / 'images'))

# init config to setup required env variables
# Config()
