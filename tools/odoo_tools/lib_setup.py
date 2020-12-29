import shutil
import subprocess
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __replace_in_file
from .tools import _sanity_check
from .tools import __get_odoo_commit
from .tools import _fix_permissions
from .tools import _askcontinue
from .tools import remove_webassets
from . import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from . import Commands

@cli.group(cls=AliasedGroup)
@pass_config
def setup(config):
    pass

@setup.command()
@pass_config
def doctor(config):
    _sanity_check(config)

@setup.command()
@pass_config
@click.pass_context
def show_effective_settings(ctx, config):
    from . import MyConfigParser
    config = MyConfigParser(config.files['settings'])
    for k in sorted(config.keys()):
        click.echo("{}={}".format(
            k,
            config[k]
        ))


@setup.command(name="remove-web-assets")
@pass_config
@click.pass_context
def remove_web_assets(ctx, config):
    """
    if odoo-web interface is broken (css, js) then purging the web-assets helps;
    they are usually recreated when admin login
    """
    from .odoo_config import current_version
    _askcontinue(config)
    conn = config.get_odoo_conn().clone(dbname=config.dbname)
    remove_webassets(conn)
    if current_version() <= 10.0:
        click.echo("Please login as admin, so that assets are recreated.")

@setup.command()
@pass_config
def status(config):
    color = 'yellow'
    click.secho("projectname: ", nl=False)
    click.secho(config.PROJECT_NAME, fg=color, bold=True)
    click.secho("version: ", nl=False)
    click.secho(config.odoo_version, fg=color, bold=True)
    click.secho("db: ", nl=False)
    click.secho(config.dbname, fg=color, bold=True)

@setup.command()
@pass_config
def fix_permissions(config):
    _fix_permissions(config)


Commands.register(status)
Commands.register(fix_permissions)
