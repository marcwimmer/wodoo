import subprocess
import inquirer
import traceback
from datetime import datetime
import time
import shutil
import hashlib
import os
import tempfile
import click
from .tools import DBConnection
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_table
from .tools import __get_odoo_commit
from .tools import __start_postgres_and_wait
from .tools import __cmd_interactive
from .tools import __get_installed_modules
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __execute_sql

@cli.group(cls=AliasedGroup)
@pass_config
def odoo_module(config):
    pass

@odoo_module.command(name='abort-upgrade')
@pass_config
def abort_upgrade(config):
    click.echo("Aborting upgrade...")
    SQL = """
        UPDATE ir_module_module SET state = 'installed' WHERE state = 'to upgrade';
        UPDATE ir_module_module SET state = 'uninstalled' WHERE state = 'to install';
    """
    __execute_sql(config.get_odoo_conn(), SQL)

@odoo_module.command(name='unlink')
def module_unlink():
    for file in (dirs['customs'] / 'links').glob("*"):
        if file.is_symlink():
            file.unlink()

def _get_default_modules_to_update():
    from module_tools.module_tools import Modules, DBModules
    mods = Modules()
    module = mods.get_customs_modules('to_update')
    module += DBModules.get_uninstalled_modules_where_others_depend_on()
    module += DBModules.get_uninstalled_modules_that_are_auto_install_and_should_be_installed()
    return module

@odoo_module.command(name='update-ast-file')
def update_ast_file():
    from module_tools.odoo_parser import update_cache
    update_cache()

@odoo_module.command(name='update-module-file')
@click.argument('module', nargs=-1, required=True)
def update_module_file(module):
    from module_tools.module_tools import Module
    for module in module:
        Module.get_by_name(module).update_module_file()

@odoo_module.command()
@click.argument('module', nargs=-1, required=False)
@click.option('--installed-modules', '-i', default=False, is_flag=True, help="Updates only installed modules")
@click.option('--dangling-modules', '-d', default=False, is_flag=True, help="Updates only dangling modules")
@click.option('--no-update-module-list', '-n', default=False, is_flag=True, help="Does not install/update module list module")
@click.option('--non-interactive', '-I', default=True, is_flag=True, help="Not interactive")
@click.option('--check-install-state', default=True, is_flag=True, help="Check for dangling modules afterwards")
@click.option('--no-restart', default=False, is_flag=True, help="If set, no machines are restarted afterwards")
@click.option('--no-dangling-check', default=False, is_flag=True, help="Not checking for dangling modules")
@click.option('--i18n', default=False, is_flag=True, help="Overwrite Translations")
@pass_config
@click.pass_context
def update(ctx, config, module, dangling_modules, installed_modules, non_interactive, no_update_module_list, no_dangling_check=False, check_install_state=True, no_restart=True, i18n=False):
    """
    Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)
    Minimal downtime;

    To update all (custom) modules set "all" here
    """
    # ctx.invoke(module_link)
    Commands.invoke(ctx, 'wait_for_container_postgres')
    module = list(filter(lambda x: x, sum(map(lambda x: x.split(','), module), [])))  # '1,2 3' --> ['1', '2', '3']

    if not module:
        module = _get_default_modules_to_update()

    if not no_dangling_check:
        if any(x[1] == 'uninstallable' for x in __get_dangling_modules()):
            for x in __get_dangling_modules():
                click.echo("{}: {}".format(*x[:2]))
            if non_interactive or input("Uninstallable modules found - shall I set them to 'uninstalled'? [y/N]").lower() == 'y':
                __execute_sql(config.get_odoo_conn(), "update ir_module_module set state = 'uninstalled' where state = 'uninstallable';")
        if __get_dangling_modules() and not dangling_modules:
            if not no_dangling_check:
                Commands.invoke(ctx, 'show_install_state', suppress_error=True)
                input("Abort old upgrade and continue? (Ctrl+c to break)")
                ctx.invoke(abort_upgrade)
    if installed_modules:
        module += __get_installed_modules(config)
    if dangling_modules:
        module += [x[0] for x in __get_dangling_modules()]
    module = list(filter(lambda x: x, module))
    if not module:
        raise Exception("no modules to update")

    click.echo("Run module update")
    if config.odoo_update_start_notification_touch_file_in_container:
        with open(config.odoo_update_start_notification_touch_file_in_container, 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        params = ['run', 'odoo_update', '/update_modules.py', ','.join(module)]
        if non_interactive:
            params += ['--non-interactive']
        if not no_update_module_list:
            params += ['--no-update-modulelist']
        if no_dangling_check:
            params += ['no-dangling-check']
        if i18n:
            params += ['--i18n']
        __cmd_interactive(*params)
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if check_install_state:
        ctx.invoke(show_install_state, suppress_error=no_dangling_check)

    if not no_restart:
        Commands.invoke(ctx, 'up', daemon=True)
        if config.run_proxy:
            Commands.invoke(ctx, 'proxy_reload')

    Commands.invoke(ctx, 'status')
    if config.odoo_update_start_notification_touch_file_in_container:
        with open(config.odoo_update_start_notification_touch_file_in_container, 'w') as f:
            f.write("0")

@odoo_module.command(name="update-i18n", help="Just update translations")
@click.argument('module', nargs=-1, required=False)
@click.option('--no-restart', default=False, is_flag=True, help="If set, no machines are restarted afterwards")
@pass_config
@click.pass_context
def update_i18n(ctx, config, module, no_restart):
    Commands.invoke(ctx, 'wait_for_container_postgres')
    module = list(filter(lambda x: x, sum(map(lambda x: x.split(','), module), [])))  # '1,2 3' --> ['1', '2', '3']

    if not module:
        module = _get_default_modules_to_update()

    try:
        params = ['run', 'odoo_update', '/update_modules.py', ','.join(module)]
        params += ['--non-interactive']
        params += ['--no-update-modulelist']
        params += ['no-dangling-check']
        params += ['--only-i18n']
        __cmd_interactive(*params)
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if not no_restart:
        Commands.invoke(ctx, 'restart', machines=['odoo'])

@odoo_module.command(name='remove-old')
@click.option("--ask-confirm", default=True, is_flag=True)
@pass_config
@click.pass_context
def remove_old_modules(ctx, config, ask_confirm=True):
    """
    Sets modules to 'uninstalled', that have no module dir anymore.
    """
    from module_tools.module_tools import get_manifest_path_of_module_path
    from module_tools.odoo_config import get_odoo_addons_paths
    from module_tools.odoo_config import get_links_dir
    click.echo("Analyzing which modules to remove...")
    Commands.invoke(ctx, 'wait_for_container_postgres')
    mods = sorted(map(lambda x: x[0], __execute_sql(config.get_odoo_conn(), "select name from ir_module_module where state in ('installed', 'to install', 'to upgrade') or auto_install = true;", fetchall=True)))
    mods = list(filter(lambda x: x not in ('base'), mods))
    to_remove = []
    for mod in mods:
        for path in get_odoo_addons_paths() + [get_links_dir()]:
            if get_manifest_path_of_module_path(path / mod):
                break
        else:
            to_remove.append(mod)
    if not to_remove:
        click.echo("Nothing found to remove")
        return
    click.echo("Following modules are set to uninstalled:")
    for mod in to_remove:
        click.echo(mod)
    if ask_confirm:
        answer = inquirer.prompt([inquirer.Confirm('confirm', message="Continue?", default=True)])
        if not answer or not answer['confirm']:
            return
    for mod in to_remove:
        __execute_sql(config.get_odoo_conn(), "update ir_module_module set auto_install=false, state = 'uninstalled' where name = '{}'".format(mod))
        click.echo("Set module {} to uninstalled.".format(mod))

@odoo_module.command()
@pass_config
def progress(config):
    """
    Displays installation progress
    """
    for row in __execute_sql(config.get_odoo_conn(), "select state, count(*) from ir_module_module group by state;", fetchall=True):
        click.echo("{}: {}".format(row[0], row[1]))

@odoo_module.command(name='show-install-state')
@pass_config
def show_install_state(config, suppress_error=False):
    dangling = __get_dangling_modules()
    if dangling:
        click.echo("Displaying dangling modules:")
    for row in dangling:
        click.echo("{}: {}".format(row[0], row[1]))

    if dangling and not suppress_error:
        raise Exception("Dangling modules detected - please fix installation problems and retry!")

def __get_extra_install_modules():
    path = dirs['odoo_home'] / 'extra_install' / 'modules'
    if not path.exxists():
        return {}
    with open(path, 'r') as f:
        return eval(f.read())

def __get_subtree_url(type, submodule):
    assert type in ['common', 'extra_install']
    if type == 'common':
        url = 'git.clear-consulting.de:/odoo/modules/{}'.format(submodule)
    elif type == 'extra_install':
        data = __get_extra_install_modules()
        url = data[submodule]['url']
    else:
        raise Exception("impl")
    return url

@pass_config
def __get_dangling_modules(config):
    conn = config.get_odoo_conn()
    if not __exists_table(conn, 'ir_module_module'):
        return []

    rows = __execute_sql(
        conn,
        sql="SELECT name, state from ir_module_module where state not in ('installed', 'uninstalled', 'uninstallable');",
        fetchall=True
    )
    return rows

@odoo_module.command(name='show-addons-paths')
def show_addons_paths():
    from module_tools.odoo_config import get_odoo_addons_paths
    paths = get_odoo_addons_paths()
    for path in paths:
        click.echo(path)

@odoo_module.command(name='fetch', help="Walks into source code directory and pull latest branch version.")
def fetch_latest_revision():
    from module_tools.odoo_config import get_links_dir
    from module_tools.odoo_config import customs_dir

    subprocess.call([
        "git",
        "pull",
    ], cwd=customs_dir())

    subprocess.check_call([
        "git",
        "checkout",
        "-f",
    ], cwd=customs_dir())

    subprocess.call([
        "git",
        "status",
    ], cwd=customs_dir())

@odoo_module.command(name='pretty-print-manifest')
def pretty_print_manifest():
    from module_tools.odoo_config import MANIFEST
    from module_tools.odoo_config import MANIFEST_update
    MANIFEST().rewrite()

@odoo_module.command(name='show-conflicting-modules')
def show_conflicting_modules():
    from module_tools.odoo_config import get_odoo_addons_paths
    get_odoo_addons_paths(show_conflicts=True)


Commands.register(progress)
Commands.register(remove_old_modules)
Commands.register(update)
Commands.register(show_install_state)
