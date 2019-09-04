from pathlib import Path
import subprocess
import sys
from datetime import datetime
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import _askcontinue
from .tools import __append_line
from .tools import __get_odoo_commit
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass

@src.command(name='make-customs')
@pass_config
@click.pass_context
def src_make_customs(ctx, config, customs, version):
    raise Exception("rework - add fetch sha")

@src.command()
@pass_config
def make_module(config, name):
    cwd = config.working_dir
    from .module_tools import make_module as _tools_make_module
    _tools_make_module(
        cwd,
        name,
    )

@src.command(name='update-ast')
def update_ast():
    from .odoo_parser import update_cache
    started = datetime.now()
    click.echo("Updating ast - can take about one minute")
    update_cache()
    click.echo("Updated ast - took {} seconds".format((datetime.now() - started).seconds))


@src.command()
def rmpyc():
    for file in dirs['customs'].glob("**/*.pyc"):
        file.unlink()

@src.command(name='odoo')
@click.pass_context
def checkout_odoo(ctx, version='', not_use_local_repo=True, commit_changes=False, force=False):
    """
    Puts odoo from repos into subfolder 'odoo'.

    Can used for migration tests:
     - temporary switch to odoo version

    """
    from .module_tools.odoo_config import current_version
    __assert_file_exists(dirs['customs'] / '.version')

    if (dirs['customs'] / 'odoo').is_dir() and not force:
        raise Exception("Odoo already exists")

    if not version:
        version = current_version()
    version = float(version)

    subprocess.check_call([
        'git',
        'status',
    ], cwd=dirs['customs'])
    odoo_path = dirs['customs'] / 'odoo'
    if odoo_path.exists():
        shutil.rmtree(odoo_path)
        if commit_changes:
            subprocess.check_call([
                'git',
                'add',
                '.'
            ], cwd=dirs['customs'])
            subprocess.check_call([
                'git',
                'commit',
                '-am "removed current odoo"'
            ], cwd=dirs['customs'])

    if not_use_local_repo:
        url = '/opt/odoo/repos/odoo'
    else:
        url = 'https://github.com/odoo/odoo'
    subprocess.check_call([
        'git',
        'clone',
        url,
        '--branch',
        str(version),
        '--single-branch',
        'odoo',
    ], cwd=dirs['customs'])
    sha = subprocess.check_output([
        'git',
        'rev-parse',
        "HEAD",
    ], cwd=odoo_path).strip()

    shutil.rmtree(dirs['customs'] / 'odoo/.git')
    (dirs['customs'] / '.version').write_text(str(version))
    (dirs['customs'] / 'odoo.commit').write_text(sha.strip())
    reload() # apply new version
    Commands.invoke(ctx, 'status')

@src.command()
@click.pass_context
def fetch(ctx):
    """
    Fetches latest source (used on production systems fetching from deployment source)
    """
    subprocess.call([
        'git',
        'pull',
    ], cwd=dirs['customs'])
