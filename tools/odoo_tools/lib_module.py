import sys
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
from .tools import __dcrun
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import _exists_table
from .tools import __get_odoo_commit
from .tools import _start_postgres_and_wait
from .tools import __cmd_interactive
from .tools import __get_installed_modules
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import _execute_sql
from .tools import get_services
from pathlib import Path

class UpdateException(Exception): pass

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
    _execute_sql(config.get_odoo_conn(), SQL)

def _get_default_modules_to_update():
    from .module_tools import Modules, DBModules
    mods = Modules()
    module = mods.get_customs_modules('to_update')
    module += DBModules.get_uninstalled_modules_where_others_depend_on()
    return module

@odoo_module.command(name='update-ast-file')
def update_ast_file():
    from .odoo_parser import update_cache
    update_cache()

@odoo_module.command(name='update-module-file')
@click.argument('module', nargs=-1, required=True)
def update_module_file(module):
    from .module_tools import Module
    for module in module:
        Module.get_by_name(module).update_module_file()

@odoo_module.command(name='run-tests')
@pass_config
@click.pass_context
def run_tests(ctx, config):
    started = datetime.now()
    if not config.devmode:
        click.secho("Devmode required to run unit tests. Database will be destroyed.", fg='red')
        sys.exit(-1)

    if not config.force:
        click.secho("Please provide parameter -f - database will be dropped. Otherwise tests are run against existing db. \n\nodoo -f run-tests", fg='yellow')

    from .odoo_config import MANIFEST
    tests = MANIFEST().get('tests', [])
    if not tests:
        click.secho("No test files found!")
        return

    if config.force:
        Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
        Commands.invoke(ctx, 'reset-db')
        Commands.invoke(ctx, 'update', "", tests=False, no_dangling_check=True)

    from .module_tools import Module
    from .odoo_config import customs_dir

    success, failed = [], []
    for module in tests:
        module = Module.get_by_name(module)
        testfiles = list(module.get_all_files_of_module())
        testfiles = [x for x in testfiles if str(x).startswith("tests/")]
        testfiles = [x for x in testfiles if str(x).endswith('.py')]
        testfiles = [x for x in testfiles if x.name != '__init__.py']
        testfiles = [x for x in testfiles if x.name.startswith("test_")]

        # identify test files and run them, otherwise tests of dependent modules are run
        for file in sorted(testfiles):
            mfpath = module.manifest_path.parent
            file = mfpath.relative_to(customs_dir()) / file
            if config.use_docker:
                params = ['odoo', '/odoolib/unit_test.py', f'{file}']
                click.secho(f"Running test: {file}", fg='yellow', bold=True)
                res = __dcrun(params + ['--log-level=error', '--not-interactive'], raise_exception=True, returncode=True)
                if res:
                    failed.append(file)
                    click.secho(f"Failed, running again with debug on: {file}", fg='red', bold=True)
                    res = __cmd_interactive(*(['run', '--rm'] + params + ['--log-level=debug']))
                else:
                    success.append(file)

    elapsed = datetime.now() - started
    click.secho(f"Time: {elapsed}", fg='yellow')

    # in force-mode shut down
    if config.force:
        Commands.invoke(ctx, 'down', volumes=True)

    if failed:
        click.secho("Tests failed: ", fg='red')
        for mod in failed:
            click.secho(str(mod), fg='red')
        sys.exit(-1)
    else:
        for mod in success:
            click.secho(str(mod), fg='green')
        click.secho("Tests OK", fg='green')


@odoo_module.command()
@click.argument('module', nargs=-1, required=False)
@click.option('--installed-modules', '-i', default=False, is_flag=True, help="Updates only installed modules")
@click.option('--dangling-modules', '-d', default=False, is_flag=True, help="Updates only dangling modules")
@click.option('--no-update-module-list', '-n', default=False, is_flag=True, help="Does not install/update module list module")
@click.option('--non-interactive', '-I', default=True, is_flag=True, help="Not interactive")
@click.option('--check-install-state', default=True, is_flag=True, help="Check for dangling modules afterwards")
@click.option('--no-restart', default=False, is_flag=True, help="If set, no machines are restarted afterwards")
@click.option('--no-dangling-check', default=False, is_flag=True, help="Not checking for dangling modules")
@click.option('--tests', default=False, is_flag=True, help="Runs tests")
@click.option('--i18n', default=False, is_flag=True, help="Overwrite Translations")
@pass_config
@click.pass_context
def update(ctx, config, module, dangling_modules, installed_modules, non_interactive, no_update_module_list, no_dangling_check=False, check_install_state=True, no_restart=True, i18n=False, tests=False):
    """
    Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)
    Minimal downtime;

    To update all (custom) modules set "all" here
    """
    from .module_tools import Modules, DBModules
    # ctx.invoke(module_link)
    Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)
    module = list(filter(lambda x: x, sum(map(lambda x: x.split(','), module), [])))  # '1,2 3' --> ['1', '2', '3']

    if not no_restart:
        if config.use_docker:
            Commands.invoke(ctx, 'kill', machines=get_services(config, 'odoo_base'))
            if config.run_redis:
                Commands.invoke(ctx, 'up', machines=['redis'], daemon=True)
            Commands.invoke(ctx, 'wait_for_container_postgres')

    if not module:
        module = _get_default_modules_to_update()

    if not no_dangling_check:
        if any(x[1] == 'uninstallable' for x in DBModules.get_dangling_modules()):
            for x in DBModules.get_dangling_modules():
                click.echo("{}: {}".format(*x[:2]))
            if non_interactive or input("Uninstallable modules found - shall I set them to 'uninstalled'? [y/N]").lower() == 'y':
                _execute_sql(config.get_odoo_conn(), "update ir_module_module set state = 'uninstalled' where state = 'uninstallable';")
        if DBModules.get_dangling_modules() and not dangling_modules:
            if not no_dangling_check:
                Commands.invoke(ctx, 'show_install_state', suppress_error=True)
                input("Abort old upgrade and continue? (Ctrl+c to break)")
                ctx.invoke(abort_upgrade)
    if installed_modules:
        module += __get_installed_modules(config)
    if dangling_modules:
        module += [x[0] for x in DBModules.get_dangling_modules()]
    module = list(filter(lambda x: x, module))
    if not module:
        raise Exception("no modules to update")

    click.echo("Run module update")
    if config.odoo_update_start_notification_touch_file_in_container:
        with open(config.odoo_update_start_notification_touch_file_in_container, 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        params = [','.join(module)]
        if non_interactive:
            params += ['--non-interactive']
        if not no_update_module_list:
            params += ['--no-update-modulelist']
        if no_dangling_check:
            params += ['no-dangling-check']
        if i18n:
            params += ['--i18n']
        if not tests:
            params += ['--no-tests']
        rc = _exec_update(config, params)
        if rc:
            raise UpdateException(module)

    except UpdateException:
        raise
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if check_install_state:
        ctx.invoke(show_install_state, suppress_error=no_dangling_check)

    if not no_restart and config.use_docker:
        Commands.invoke(ctx, 'restart', machines=['odoo'])
        if config.run_odoocronjobs:
            Commands.invoke(ctx, 'restart', machines=['odoo_cronjobs'])
        if config.run_queuejobs:
            Commands.invoke(ctx, 'restart', machines=['odoo_queuejobs'])
        Commands.invoke(ctx, 'up', daemon=True)

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
        params = [','.join(module)]
        params += ['--non-interactive']
        params += ['--no-update-modulelist']
        params += ['no-dangling-check']
        params += ['--only-i18n']
        _exec_update(config, params)
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if not no_restart:
        Commands.invoke(ctx, 'restart', machines=['odoo'])


@odoo_module.command()
@pass_config
def progress(config):
    """
    Displays installation progress
    """
    for row in _execute_sql(config.get_odoo_conn(), "select state, count(*) from ir_module_module group by state;", fetchall=True):
        click.echo("{}: {}".format(row[0], row[1]))

@odoo_module.command(name='show-install-state')
@pass_config
def show_install_state(config, suppress_error=False):
    from .module_tools import DBModules
    dangling = DBModules.get_dangling_modules()
    if dangling:
        click.echo("Displaying dangling modules:")
    for row in dangling:
        click.echo("{}: {}".format(row[0], row[1]))

    if dangling and not suppress_error:
        raise Exception("Dangling modules detected - please fix installation problems and retry!")

@odoo_module.command(name='show-addons-paths')
def show_addons_paths():
    from .odoo_config import get_odoo_addons_paths
    paths = get_odoo_addons_paths()
    for path in paths:
        click.echo(path)

@odoo_module.command(name='pretty-print-manifest')
def pretty_print_manifest():
    from .odoo_config import MANIFEST
    MANIFEST().rewrite()

@odoo_module.command(name='show-conflicting-modules')
def show_conflicting_modules():
    from .odoo_config import get_odoo_addons_paths
    get_odoo_addons_paths(show_conflicts=True)

def _exec_update(config, params):
    if config.use_docker:
        params = ['run', 'odoo_update', '/update_modules.py'] + params
        return __cmd_interactive(*params)
    else:
        from . import lib_control_native
        return lib_control_native._update_command(config, params)

@odoo_module.command()
@click.option('-r', '--repeat', is_flag=True)
@pass_config
def unittest(config, repeat):
    """
    Collects unittest files and offers to run
    """
    from .odoo_config import MANIFEST, CUSTOMS_MANIFEST_FILE
    from .module_tools import Module
    from pathlib import Path
    last_unittest = config.runtime_settings.get('last_unittest')

    if repeat and last_unittest:
        filename = last_unittest
    else:
        testfiles = []

        for testmodule in MANIFEST().get('tests', []):
            testmodule = Module.get_by_name(testmodule)
            for file in testmodule.path.glob("tests/test*.py"):
                testfiles.append(file.relative_to(CUSTOMS_MANIFEST_FILE().parent))

        testfiles = sorted(testfiles)
        message = "Please choose the unittest to run."
        filename = inquirer.prompt([inquirer.List('filename', message, choices=testfiles)]).get('filename')

    if not filename:
        return
    config.runtime_settings.set('last_unittest', filename)
    click.secho(str(filename), fg='green', bold=True)
    container_file = Path('/opt/src/') / filename
    params = ['odoo', '/odoolib/unit_test.py', f'{container_file}']
    __dcrun(params + ['--log-level=debug'], interactive=True)

@odoo_module.command()
@click.argument("name", required=True)
@pass_config
@click.pass_context
def set_ribbon(ctx, config, name):
    SQL = """
        Select state from ir_module_module where name = 'web_environment_ribbon';
    """
    res = _execute_sql(config.get_odoo_conn(), SQL, fetchone=True)
    if not (res and res[0] == 'installed'):
        Commands.invoke(ctx, 'update', module=['web_environment_ribbon'])

    _execute_sql(config.get_odoo_conn(), """
        UPDATE
            ir_config_parameter
        SET
            value = %s
        WHERE
            key = 'ribbon.name';
    """, params=(name,))


@odoo_module.command(help="For directly installed odoos.")
@pass_config
@click.pass_context
def generate_update_command(ctx, config):
    modules = _get_default_modules_to_update()

    click.secho(f"-u {','.join(modules)}")


@pass_config
@click.option('-s', '--start')
@click.pass_context
def list_changed_modules(ctx, config, start):
    from .lib_module import Module
    filepaths = subprocess.check_output([
        'git',
        'diff',
        f"{start}..HEAD",
        "--name-only",
    ]).decode('utf-8').split("\n")
    modules = []
    root = Path(os.getcwd())
    for filepath in filepaths:
        filepath = root / filepath
        try:
            module = Module(filepath)
        except Module.IsNot:
            pass
        else:
            modules.append(module.name)
    for module in modules:
        click.secho(module)


Commands.register(progress)
Commands.register(update)
Commands.register(show_install_state)
