import sys
import json
import base64
import subprocess
import inquirer
from git import Repo
import traceback
from datetime import datetime
import shutil
import os
import tempfile
import click
from .tools import sync_folder
from .tools import __dcrun
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
    module += DBModules.get_outdated_installed_modules(mods)
    return module

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
                res = __dcrun(params + ['--log-level=error', '--not-interactive'], returncode=True)
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

@odoo_module.command(name='download-openupgrade')
@pass_config
@click.option('--version', help="Destination Version", required=True)
@click.pass_context
def download_openupgrade(ctx, config, version):
    dir_openupgrade = Path(tempfile.mktemp())
    subprocess.check_call(['/usr/bin/git', 'clone', '--depth', '1', '--branch', version, 'https://github.com/OCA/OpenUpgrade', dir_openupgrade / 'openupgrade'])

    if float(version) < 14.0:
        destination_path = 'odoo'
    else:
        destination_path = 'openupgrade'

    sync_folder(
        dir_openupgrade / 'openupgrade',
        config.dirs['customs'] / destination_path,
        excludes=['.git'],
    )
    shutil.rmtree(dir_openupgrade)

def _add_outdated_versioned_modules(modules):
    """

    Gets dependency tree of modules and copmares version in manifest with version in database.
    If db is newer then update is required.

    This usually habens after an update of odoo core.
    
    """
    from .module_tools import Modules, DBModules
    from .odoo_config import MANIFEST
    mods = Modules()

    for module in modules:
        yield module
        if module == 'base':
            continue

        for dep in mods.get_module_flat_dependency_tree(mods.modules[module]):
            meta_info = DBModules.get_meta_data(dep)
            if not meta_info:
                continue
            version = meta_info['version']
            if not version:
                continue
            version = tuple([int(x) for x in version.split(".")])
            new_version = mods.modules[dep].manifest_dict.get('version')
            if not new_version:
                continue
            new_version = tuple([int(x) for x in new_version.split('.')])
            if len(new_version) == 2:
                # add odoo version in front
                new_version = tuple([int(x) for x in str(MANIFEST()['version']).split('.')] + list(new_version))

            if new_version > version:
                yield dep


@odoo_module.command()
@click.argument('migration-file', required=True)
@click.argument('mode', required=True)
@click.option('--allow-serie', is_flag=True)
@click.option('--force-version')
@pass_config
@click.pass_context
def marabunta(ctx, config, migration_file, mode, allow_serie, force_version):
    click.secho("""
            _.._.-..-._
        .-'  .'  /\\  \\`._
        /    /  .'  `-.\\  `.
            :_.'  ..    :       _.../\\
            |           ;___ .-'   //\\\\.
            \\  _..._  /    `/\\   //  \\\\\\
            `-.___.-'  /\\ //\\\\       \\\\:
                |    //\\V/ :\\\\       \\\\
                    \\      \\\\/  \\\\      /\\\\
                    `.____.\\\\   \\\\   .'  \\\\
                    //   /\\\\---\\\\-'     \\\\
                fsc  //   // \\\\   \\\\       \\\\
    """, fg='red')

    click.secho("=================================", fg='yellow')
    click.secho("MARABUNTA", fg='yellow')
    click.secho("=================================", fg='yellow')
    params = [
        '--migration-file', '/opt/src/' + migration_file,
        '--database', config.dbname,
        '--db-user', config.db_user,
        '--db-password', config.db_pwd,
        '--db-port', config.db_port,
        '--db-host', config.db_host,
        '--mode', mode,
    ]
    if allow_serie:
        params += ["--allow-serie"]
    if force_version:
        params += ["--force-version", force_version]
    
    params = ['run', 'odoo', '/usr/local/bin/marabunta'] + params
    return __cmd_interactive(*params)


@odoo_module.command()
@click.argument('module', nargs=-1, required=False)
@click.option('--since-git-sha', '-i', default=None, is_flag=False, help="Extracts modules changed since this git sha and updates them")
@click.option('--installed-modules', '-i', default=False, is_flag=True, help="Updates only installed modules")
@click.option('--dangling-modules', '-d', default=False, is_flag=True, help="Updates only dangling modules")
@click.option('--no-update-module-list', '-n', default=False, is_flag=True, help="Does not install/update module list module")
@click.option('--non-interactive', '-I', default=True, is_flag=True, help="Not interactive")
@click.option('--check-install-state', default=True, is_flag=True, help="Check for dangling modules afterwards")
@click.option('--no-restart', default=False, is_flag=True, help="If set, no machines are restarted afterwards")
@click.option('--no-dangling-check', default=False, is_flag=True, help="Not checking for dangling modules")
@click.option('--tests', default=False, is_flag=True, help="Runs tests")
@click.option('--i18n', default=False, is_flag=True, help="Overwrite Translations")
@click.option('--no-install-server-wide-first', default=False, is_flag=True)
@click.option('--no-extra-addons-paths', is_flag=True)
@click.option('-c', '--config-file', default='config_update', help="Specify config file to use, for example config_update")
@click.option('--server-wide-modules')
@click.option('--additional-addons-paths')
@click.option('--uninstall', is_flag=True, help="Executes just uninstallation of modules.")
@pass_config
@click.pass_context
def update(
    ctx, config, module,
    since_git_sha, dangling_modules, installed_modules,
    non_interactive, no_update_module_list, no_install_server_wide_first,
    no_extra_addons_paths, no_dangling_check=False, check_install_state=True,
    no_restart=True, i18n=False, tests=False,
    config_file=False, server_wide_modules=False, additional_addons_paths=False,
    uninstall=False
    ):
    """
    Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)
    Minimal downtime;

    To update all (custom) modules set "all" here


    Sample call migration 14.0:
    odoo update --no-dangling-check --config-file=config_migration --server-wide-modules=web,openupgrade_framework --additional-addons-paths=openupgrade base



    """
    click.secho("""

           _                               _       _       
          | |                             | |     | |      
  ___   __| | ___   ___    _   _ _ __   __| | __ _| |_ ___ 
 / _ \\ / _` |/ _ \\ / _ \\  | | | | '_ \\ / _` |/ _` | __/ _ \\
| (_) | (_| | (_) | (_) | | |_| | |_) | (_| | (_| | ||  __/
 \\___/ \\__,_|\\___/ \\___/   \\__,_| .__/ \\__,_|\\__,_|\\__\\___|
                                | |                        
                                |_|   
    """, fg='green')
    from .module_tools import Modules, DBModules
    # ctx.invoke(module_link)
    if config.run_postgres:
        Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
        Commands.invoke(ctx, 'wait_for_container_postgres', missing_ok=True)

    if not uninstall:
        if since_git_sha and module:
            raise Exception("Conflict: since-git-sha and modules")
        if since_git_sha:
            module = list(_get_changed_modules(since_git_sha))

            # filter modules to defined ones in MANIFEST
            click.secho(f"Following modules change since last sha: {' '.join(module)}")
            from .odoo_config import MANIFEST
            module = list(filter(lambda x: x in MANIFEST()['install'], module))
            click.secho(f"Following modules change since last sha (filtered to manifest): {' '.join(module)}")

            if not module:
                click.secho("No module update required - exiting.")
                return
        else:
            module = list(filter(lambda x: x, sum(map(lambda x: x.split(','), module), [])))  # '1,2 3' --> ['1', '2', '3']

        if not module and not since_git_sha:
            module = _get_default_modules_to_update()

        module = list(set(_add_outdated_versioned_modules(module)))

        if not no_restart:
            if config.use_docker:
                Commands.invoke(ctx, 'kill', machines=get_services(config, 'odoo_base'))
                if config.run_redis:
                    Commands.invoke(ctx, 'up', machines=['redis'], daemon=True)
                if config.run_postgres:
                    Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
                Commands.invoke(ctx, 'wait_for_container_postgres')

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
            if no_extra_addons_paths:
                params += ['--no-extra-addons-paths']
            if non_interactive:
                params += ['--non-interactive']
            if no_install_server_wide_first:
                params += ['--no-install-server-wide-first']
            if no_update_module_list:
                params += ['--no-update-modulelist']
            if no_dangling_check:
                params += ['--no-dangling-check']
            if i18n:
                params += ['--i18n']
            if not tests:
                params += ['--no-tests']
            if server_wide_modules:
                params += ['--server-wide-modules', server_wide_modules]
            if additional_addons_paths:
                params += ['--additional-addons-paths', additional_addons_paths]
            params += ["--config-file=" + config_file]
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

    def _uninstall_marked_modules():
        """
        Checks for file "uninstall" in customs root and sets modules to uninstalled.
        """
        from .odoo_config import MANIFEST
        if float(config.odoo_version) < 11.0:
            return
        # check if something is todo
        to_uninstall = MANIFEST().get('uninstall', [])
        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            click.secho("Going to uninstall {}".format(', '.join(to_uninstall)), fg='red')

            if config.use_docker:
                from .lib_control_with_docker import shell as lib_shell
            for module in to_uninstall:
                click.secho(f"Uninstall {module}", fg='red')
                lib_shell("""
self.env['ir.module.module'].search([
('name', '=', '{}'),
('state', 'in', ['to upgrade', 'to install', 'installed'])
]).module_uninstall()
self.env.cr.commit()
                """.format(module))

        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            click.secho(f"Failed to uninstall: {','.join(to_uninstall)}", fg='red')
            sys.exit(-1)

    _uninstall_marked_modules()

@odoo_module.command(name="update-i18n", help="Just update translations")
@click.argument('module', nargs=-1, required=False)
@click.option('--no-restart', default=False, is_flag=True, help="If set, no machines are restarted afterwards")
@pass_config
@click.pass_context
def update_i18n(ctx, config, module, no_restart):
    if config.run_postgres:
        Commands.invoke(ctx, 'up', machines=['postgres'], daemon=True)
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
    get_odoo_addons_paths()

def _exec_update(config, params):
    if config.use_docker:
        params = ['run', 'odoo_update', '/update_modules.py'] + params
        return __cmd_interactive(*params)
    else:
        from . import lib_control_native
        return lib_control_native._update_command(config, params)


@odoo_module.command()
@click.argument('file', required=False)
@click.option('-u', '--user', default='admin')
@click.option('-a', '--all', is_flag=True)
@click.option('-t', '--tag', is_flag=False)
@click.option('-n', '--test_name', is_flag=False)
@pass_config
def robotest(config, file, user, all, tag, test_name):
    from .odoo_config import MANIFEST, MANIFEST_FILE
    from .module_tools import Module
    from pathlib import Path
    from .odoo_config import customs_dir
    from .robo_helpers import _make_archive

    if not config.devmode:
        click.secho("Devmode required to run unit tests. Database will be destroyed.", fg='red')
        sys.exit(-1)

    testfiles = _get_all_robottest_files()

    if file and all:
        click.secho("Cannot provide all and file together!", fg='red')
        sys.exit(-1)

    if file:
        if '/' in file:
            filename = Path(file)
        else:
            match = [x for x in testfiles if file in x.name]
            if len(match) > 1:
                click.secho("Not unique: {file}", fg='red')
                sys.exit(-1)

            if match:
                filename = match[0]

        if filename not in testfiles:
            click.secho(f"Not found: {filename}", fg='red')
            sys.exit(-1)
        filename = [filename]
    else:
        testfiles = sorted(testfiles)
        if not all:
            message = "Please choose the unittest to run."
            try:
                filename = [inquirer.prompt([inquirer.List('filename', message, choices=testfiles)]).get('filename')]
            except Exception:
                sys.exit(-1)
        else:
            filename = list(sorted(testfiles))

    if not filename:
        return

    click.secho('\n'.join(map(str, filename)), fg='green', bold=True)

    archive = _make_archive(filename, customs_dir())

    pwd = config.DEFAULT_DEV_PASSWORD
    if pwd == "True" or pwd is True:
        pwd = '1'

    def params():
        params = {
            "url": "http://proxy",
            "user": user,
            "dbname": config.DBNAME,
            "password": config.DEFAULT_DEV_PASSWORD,
            "selenium_timeout": 20, # selenium timeout,
        }
        if test_name:
            params['test_name'] = test_name
        if tag:
            params['include'] = [tag]
        return params

    data = json.dumps({
        'test_file': archive,
        'params': params(),
    })
    data = base64.encodestring(data.encode('utf-8'))

    params = [
        'robot',
    ]
    __dcrun(params, pass_stdin=data.decode('utf-8'), interactive=True)

    output_path = customs_dir() / 'robot_output'
    test_results = json.loads((output_path / 'results.json').read_text())
    failds = [x for x in test_results if x['result'] != 'ok']
    color_info = 'green'
    for failed in failds:
        color_info = 'red'
        click.secho(f"Test failed: {failed['name']} - Duration: {failed['duration']}", fg='red')
    click.secho(f"Duration: {sum(map(lambda x: x['duration'], test_results))}s", fg=color_info)
    click.secho(f"Outputs are generated in {output_path}", fg='yellow')
    click.secho(f"Watch the logs online at: http://host:{config.PROXY_PORT}/robot-output")
    if failds:
        sys.exit(-1)

def _get_all_unittest_files():
    from .odoo_config import MANIFEST, MANIFEST_FILE
    from .module_tools import Module
    testfiles = []
    for testmodule in MANIFEST().get('tests', []):
        testmodule = Module.get_by_name(testmodule)
        for _file in testmodule.path.glob("tests/test*.py"):
            testfiles.append(_file.relative_to(MANIFEST_FILE().parent))
            del _file
    return testfiles

def _get_all_robottest_files():
    from .odoo_config import MANIFEST, MANIFEST_FILE
    from .module_tools import Module
    from .odoo_config import customs_dir

    testfiles = []
    for _file in customs_dir().glob("**/*.robot"):
        if 'keywords' in _file.parts: continue
        if 'library' in _file.parts: continue
        testfiles.append(_file.relative_to(MANIFEST_FILE().parent))
        del _file
    return testfiles

@odoo_module.command()
@pass_config
def list_unit_test_files(config):
    files = _get_all_unittest_files()
    click.secho("!!!")
    for file in files:
        click.secho(file)
    click.secho("!!!")

@odoo_module.command()
@pass_config
def list_robot_test_files(config):
    files = _get_all_robottest_files()
    click.secho("!!!")
    for file in files:
        click.secho(file)
    click.secho("!!!")

@odoo_module.command()
@click.option('-r', '--repeat', is_flag=True)
@click.argument('file', required=False)
@click.option('-w', '--wait-for-remote', is_flag=True)
@click.option('-r', '--remote-debug', is_flag=True)
@pass_config
def unittest(config, repeat, file, remote_debug, wait_for_remote):
    """
    Collects unittest files and offers to run
    """
    from .odoo_config import MANIFEST, MANIFEST_FILE
    from .module_tools import Module
    from pathlib import Path
    last_unittest = config.runtime_settings.get('last_unittest')

    testfiles = _get_all_unittest_files()

    if file:
        if '/' in file:
            filename = Path(file)
        else:
            match = [x for x in testfiles if x.name == file or x.name == file + '.py']
            if match:
                filename = match[0]

        if filename not in testfiles:
            click.secho(f"Not found: {filename}", fg='red')
            sys.exit(-1)
    else:
        if repeat and last_unittest:
            filename = last_unittest
        else:
            testfiles = sorted(testfiles)
            message = "Please choose the unittest to run."
            filename = inquirer.prompt([inquirer.List('filename', message, choices=testfiles)]).get('filename')

    if not filename:
        return
    config.runtime_settings.set('last_unittest', filename)
    click.secho(str(filename), fg='green', bold=True)
    container_file = Path('/opt/src/') / filename

    interactive = True # means pudb trace turned on
    params = [
        'odoo', '/odoolib/unit_test.py', f'{container_file}',
    ]
    if wait_for_remote:
        remote_debug = True
        interactive = False
    if remote_debug:
        params += ["--remote-debug"]
    if wait_for_remote:
        params += ["--wait-for-remote"]
    if not interactive:
        params += ['--not-interactive']

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
        try:
            Commands.invoke(ctx, 'update', module=['web_environment_ribbon'], no_dangling_check=True)
        except Exception as ex:
            print(ex)

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


def _get_changed_files(git_sha):
    from .module_tools import Module
    filepaths = list(filter(bool, subprocess.check_output([
        'git',
        'diff',
        f"{git_sha}..HEAD",
        "--name-only",
    ]).decode('utf-8').split("\n")))
    repo = Repo(os.getcwd())

    # check if there are submodules:
    filepaths2 = []
    cwd = Path(os.getcwd())
    for filepath in filepaths:
        os.chdir(cwd)
        submodule = [x for x in repo.submodules if x.path == filepath]
        if submodule:
            current_commit = str(repo.active_branch.commit)
            old_commit = subprocess.check_output([
                'git', 'rev-parse', f"{git_sha}:./{filepath}"
                ]).decode("utf-8").strip()
            new_commit = subprocess.check_output([
                'git', 'rev-parse', f"{current_commit}:./{filepath}"
                ]).decode("utf-8").strip()
            # now diff the submodule
            submodule_path = cwd / filepath
            submodule_relative_path = filepath
            for filepath in list(filter(bool, subprocess.check_output([
                'git', 'diff', 
                f"{old_commit}..{new_commit}",
                "--name-only",
                ], cwd=submodule_path).decode('utf-8').split("\n"))):

                filepaths2.append(submodule_relative_path + "/" + filepath)
        else:
            filepaths2.append(filepath)

    return filepaths2
    

def _get_changed_modules(git_sha):
    from .module_tools import Module

    filepaths = _get_changed_files(git_sha)
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
    return list(sorted(set(modules)))


@odoo_module.command(name="list-changed-modules")
@click.option('-s', '--start')
@click.pass_context
@pass_config
def list_changed_modules(ctx, config, start):
    modules = _get_changed_modules(start)

    click.secho("---")
    for module in modules:
        click.secho(module)

@odoo_module.command(name="list-changed-files")
@click.option('-s', '--start')
@click.pass_context
@pass_config
def list_changed_files(ctx, config, start):
    files = _get_changed_files(start)

    click.secho("---")
    for file in files:
        click.secho(file)


Commands.register(progress)
Commands.register(update)
Commands.register(show_install_state)
