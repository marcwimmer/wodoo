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

from . import module_tools  # NOQA
from . import odoo_config  # NOQA

SCRIPT_DIRECTORY = Path(inspect.getfile(inspect.currentframe())).absolute().parent

Commands = GlobalCommands()

os.environ["HOST_HOME"] = os.getenv("HOME", "")
os.environ["ODOO_HOME"] = str(SCRIPT_DIRECTORY)


class NoProjectNameException(Exception):
    pass


def _get_default_project_name(restrict):
    def _get_project_name_from_file(path):
        if not path.exists():
            return
        pj = [x for x in path.read_text().split("\n") if "PROJECT_NAME" in x]
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
@click.option("--version", is_flag=True)
@click.option(
    "-xs",
    "--restrict-setting",
    multiple=True,
    help="Several parameters; limit to special configuration files settings and docker-compose files. All other configuration files will be ignored.",
)
@click.option(
    "-xd",
    "--restrict-docker-compose",
    multiple=True,
    help="Several parameters; limit to special configuration files settings and docker-compose files. All other configuration files will be ignored.",
)
@click.option("-p", "--project-name", help="Set Project-Name")
@click.option("--chdir", help="Set Working Directory")
@pass_config
def cli(
    config,
    force,
    verbose,
    project_name,
    restrict_setting,
    restrict_docker_compose,
    chdir,
    version,
):
    config.force = force
    config.verbose = verbose
    config.restrict = {}
    if verbose:
        os.environ["WODOO_VERBOSE"] = "1"
    if chdir:
        os.chdir(chdir)
        config.WORKING_DIR = chdir
    # if not config.WORKING_DIR:
    #     # usually all need a working except cicd
    #     if not any(x in sys.argv for x in ['init', 'install-completion']):
    #         click.secho("Please enter into an odoo directory, which contains a MANIFEST file.", fg='red')
    #         sys.exit(1)

    def _collect_files(files):
        for test in files:
            test = Path(test)
            if not test.exists():
                click.secho(f"Not found: {test}", fg="red")
                sys.exit(-1)
            yield test.absolute()

    config.restrict["settings"] = list(_collect_files(restrict_setting))
    config.restrict["docker-compose"] = list(_collect_files(restrict_docker_compose))

    if project_name:
        config.project_name = project_name
    else:
        try:
            config.project_name = _get_default_project_name(config.restrict["settings"])
        except NoProjectNameException:
            config.project_name = ""
    os.environ["project_name"] = config.project_name
    os.environ["docker_compose"] = str(config.files.get("docker_compose")) or ""
    os.environ["CUSTOMS_DIR"] = str(config.WORKING_DIR)

    load_dynamic_modules(config.dirs["images"])

    if config.verbose:
        print(config.files["docker_compose"])


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
from . import lib_venv  # NOQA
from . import lib_turnintodev  # NOQA
from . import lib_talk  # NOQA
from . import daddy_cleanup  # NOQA

# import container specific commands
from .tools import abort  # NOQA
from .tools import __dcrun  # NOQA
from .tools import __dc  # NOQA


@cli.command()
@click.option(
    "-x",
    "--execute",
    is_flag=True,
    help=("Execute the script to insert completion into users rc-file."),
)
def completion(execute):
    shell = os.environ["SHELL"].split("/")[-1]
    rc_file = Path(os.path.expanduser(f"~/.{shell}rc"))
    line = f'eval "$(_ODOO_COMPLETE={shell}_source odoo)"'
    if execute:
        content = rc_file.read_text().splitlines()
        if not list(
            filter(
                lambda x: line in x and not x.strip().startswith("#"),
                content,
            )
        ):
            content += [f"\n{line}\n"]
            click.secho(
                f"Inserted successfully\n{line}" "\n\nPlease restart you shell."
            )
            rc_file.write_text("\n".join(content))
        else:
            click.secho("Nothing done - already existed.")
    else:
        click.secho(
            "\n\n" f"Insert into {rc_file}\n\n" f"echo '{line}' >> {rc_file}" "\n\n"
        )
    sys.exit(0)


@cli.command()
@pass_config
def version(config):
    from .tools import _get_version

    version = _get_version()

    images_sha = subprocess.check_output(
        ["git", "log", "-n1", "--format=%H"], encoding="utf8", cwd=config.dirs["images"]
    ).strip()
    images_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        encoding="utf8",
        cwd=config.dirs["images"],
    ).strip()
    click.secho(
        (
            f"Wodoo Version:    {version}\n"
            f"Images SHA:       {images_sha}\n"
            f"Images Branch:    {images_branch}\n"
        ),
        fg="yellow",
    )
