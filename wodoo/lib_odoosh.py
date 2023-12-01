import click
from .tools import __dcrun
from .tools import __dcexec
from .tools import _execute_sql
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
import subprocess


@cli.group(cls=AliasedGroup)
@pass_config
def odoosh(config):
    pass


@odoosh.command(name="export")
@click.argument("ssh", required=True)
@pass_config
def fetch(config, ssh):
