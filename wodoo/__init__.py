import sys
import subprocess
from datetime import datetime
from pathlib import Path
from .click_config import Config
import imp
import inspect
import os
import shellingham

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

from . import module_tools # NOQA
from . import odoo_config  # NOQA
SCRIPT_DIRECTORY = Path(inspect.getfile(inspect.currentframe())).absolute().parent

Commands = GlobalCommands()

os.environ['HOST_HOME'] = os.getenv("HOME", "")
os.environ['ODOO_HOME'] = str(SCRIPT_DIRECTORY)

class NoProjectNameException(Exception): pass

def _get_default_project_name(restrict):
    def _get_project_name_from_file(path):
        if not path.exists():
            return
        pj = [x for x in path.read_text().split("\n") if 'PROJECT_NAME' in x]
        if pj:
            return pj[0].split("=")[-1].strip()
    if restrict:
        paths = restrict
    else:
        paths = [Path(os.path.expanduser("~/.odoo/settings"))]

    for path in paths:
        pj = _get_project_name_from_file(path)
        if pj:
            return pj

    customs_root = _get_customs_root(Path(os.getcwd()))
    if customs_root:
        root = Path(customs_root)
        if (root / "MANIFEST").exists():
            return root.name
    raise NoProjectNameException("No default project name could be determined.")

pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group(cls=AliasedGroup)
@click.option("-f", "--force", is_flag=True)
@click.option("-v", "--verbose", is_flag=True)
@click.option("-xs", '--restrict-setting', multiple=True, help="Several parameters; limit to special configuration files settings and docker-compose files. All other configuration files will be ignored.")
@click.option("-xd", '--restrict-docker-compose', multiple=True, help="Several parameters; limit to special configuration files settings and docker-compose files. All other configuration files will be ignored.")
@click.option("-p", '--project-name', help="Set Project-Name")
@click.option("--chdir", help="Set Working Directory")
@pass_config
def cli(config, force, verbose, project_name, restrict_setting, restrict_docker_compose, chdir):
    config.force = force
    config.verbose = verbose
    config.restrict = {}
    if chdir:
        os.chdir(chdir)
        config.WORKING_DIR = chdir
    if not config.WORKING_DIR:
        # usually all need a working except cicd
        if not any(x in sys.argv for x in ['init', 'install-completion']):
            click.secho("Please enter into an odoo directory, which contains a MANIFEST file.", fg='red')
            sys.exit(1)

    def _collect_files(files):
        for test in files:
            test = Path(test)
            if not test.exists():
                click.secho(f"Not found: {test}", fg='red')
                sys.exit(-1)
            yield test.absolute()

    config.restrict['settings'] = list(_collect_files(restrict_setting))
    config.restrict['docker-compose'] = list(_collect_files(restrict_docker_compose))

    if project_name:
        config.project_name = project_name
    else:
        try:
            config.project_name = _get_default_project_name(config.restrict['settings'])
        except NoProjectNameException:
            config.project_name = ""
    os.environ['project_name'] = config.project_name
    os.environ['docker_compose'] = str(config.files.get('docker_compose')) or ''

    load_dynamic_modules(config.dirs['images'])

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

# import container specific commands
from .tools import abort # NOQA
from .tools import __dcrun # NOQA
from .tools import __dc # NOQA

@cli.command()
def install_completion():
    def setup_for_shell_generic(shell, shell_call):
        path = Path(f"/etc/{shell}_completion.d")
        NAME = shell_call.upper().replace("-", "_")
        completion = subprocess.check_output([sys.argv[0]], env={f"_{NAME}_COMPLETE": f"{shell}_source"}, shell=True)
        if path.exists():
            if os.access(path, os.W_OK):
                (path / shell_call).write_bytes(completion)
                return

        if not (path / shell_call).exists():
            rc = Path(os.path.expanduser("~")) / f'.{shell}rc'
            if not rc.exists():
                return
            complete_file = rc.parent / f'.{shell_call}-completion.sh'
            complete_file.write_bytes(completion)
            if complete_file.name not in rc.read_text():
                content = rc.read_text()
                content += '\nsource ~/' + complete_file.name
                rc.write_text(content)

    name = Path(sys.argv[0]).name
    setup_for_shell_generic(shellingham.detect_shell()[0], name)
    sys.exit(0)
