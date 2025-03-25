import os
import sys
import click
import subprocess
from pathlib import Path

try:
    from .lib_clickhelpers import AliasedGroup
except ImportError:
    click = None
from .click_config import Config
from .click_global_commands import GlobalCommands

Commands = GlobalCommands()
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
    if chdir:
        chdir = Path(chdir).absolute()
        os.chdir(chdir)
        config.WORKING_DIR = chdir

    from .tools import _get_default_project_name

    if not project_name:
        try:
            project_name = _get_default_project_name(restrict_setting)
        except Exception:
            project_name = ""

    config.set_restrict("settings", restrict_setting)
    config.set_restrict("docker-compose", restrict_docker_compose)
    config.project_name = project_name


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
                f"Inserted successfully\n{line}"
                "\n\nPlease restart you shell."
            )
            rc_file.write_text("\n".join(content))
        else:
            click.secho("Nothing done - already existed.")
    else:
        click.secho(
            "\n\n"
            f"Insert into {rc_file}\n\n"
            f"echo '{line}' >> {rc_file}"
            "\n\n"
        )
    sys.exit(0)


@cli.command()
@pass_config
def version(config):
    from .tools import _get_version

    version = _get_version()

    images_sha = subprocess.check_output(
        ["git", "log", "-n1", "--format=%H"],
        encoding="utf8",
        cwd=config.dirs["images"],
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
