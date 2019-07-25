from pathlib import Path
import sys
from datetime import datetime
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import _get_platform
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
    _askcontinue(config)
    admin_dir = dirs['admin']
    Commands.invoke(ctx, 'kill')
    from module_tools.module_tools import make_customs as _tools_make_customs
    _tools_make_customs(
        customs=customs,
        version=version,
    )
    os.environ['CUSTOMS'] = customs
    cwd = dirs['odoo_home'] / 'customs' / customs
    ctx.invoke(checkout_odoo)
    odoo_dir = Path(cwd) / 'odoo'
    __system([
        'git', 'checkout', str(version)
    ], cwd=odoo_dir)
    __system([
        'git', 'checkout', str(version)
    ], cwd=admin_dir)
    __system([
        "OCA-all"
    ], cwd=admin_dir)
    __system([
        "odoo-submodule",
        'tools,web_modulesroduct_modules,calendar_ics',
    ], cwd=admin_dir)
    Commands.invoke(ctx, 'kill')
    Commands.invoke(ctx, 'compose', customs=customs)
    Commands.invoke(ctx, 'up')

@src.command()
@pass_config
def make_module(config, name):
    cwd = config.working_dir
    from module_tools.module_tools import make_module as _tools_make_module
    _tools_make_module(
        cwd,
        name,
    )

@src.command(name='update-ast')
def update_ast():
    from module_tools.odoo_parser import update_cache
    from . import PLATFORM_OSX
    if _get_platform() == PLATFORM_OSX:
        click.echo("Update is extreme slow on osx due to share performance. Please use following command natively:")
        click.echo("")
        click.echo("")
        click.echo('time PYTHONPATH=$ODOO_HOME/admin/module_tools python -c "from odoo_parser import update_cache; update_cache()"')
        click.echo("")
        click.echo("")
        sys.exit(2)
    started = datetime.now()
    click.echo("Updating ast - can take about one minute; slow on OSX due to share")
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
    __assert_file_exists(dirs['customs'] / '.version')

    if (dirs['customs'] / 'odoo').is_dir() and not force:
        raise Exception("Odoo already exists")

    if not version:
        version = __read_file(dirs['customs'] / '.version').strip()
    version = float(version)

    __system([
        'git',
        'status',
    ], cwd=dirs['customs'])
    odoo_path = dirs['customs'] / 'odoo'
    if odoo_path.exists():
        shutil.rmtree(odoo_path)
        if commit_changes:
            __system([
                'git',
                'add',
                '.'
            ], cwd=dirs['customs'])
            __system([
                'git',
                'commit',
                '-am "removed current odoo"'
            ], cwd=dirs['customs'])

    if not_use_local_repo:
        url = '/opt/odoo/repos/odoo'
    else:
        url = 'https://github.com/odoo/odoo'
    __system([
        'git',
        'clone',
        url,
        '--branch',
        str(version),
        '--single-branch',
        'odoo',
    ], cwd=dirs['customs'])
    sha = __system([
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
    __system([
        'git',
        'pull',
    ], cwd=dirs['customs'])
