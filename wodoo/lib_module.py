import sys
import uuid
import arrow
import threading
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

from wodoo.robo_helpers import _get_required_odoo_modules_from_robot_file
from .tools import get_hash
from .tools import get_directory_hash
from .tools import sync_folder
from .tools import __dcrun
from .tools import __cmd_interactive
from .tools import __get_installed_modules
from .tools import __concurrent_safe_write_file
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import _execute_sql
from .tools import get_services
from .tools import __try_to_set_owner
from .tools import measure_time, abort
from pathlib import Path


class UpdateException(Exception):
    pass


@cli.group(cls=AliasedGroup)
@pass_config
def odoo_module(config):
    pass


@odoo_module.command(name="abort-upgrade")
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
    module = mods.get_customs_modules("to_update")
    module += DBModules.get_uninstalled_modules_where_others_depend_on()
    module += DBModules.get_outdated_installed_modules(mods)
    return module


@odoo_module.command(name="update-module-file")
@click.argument("module", nargs=-1, required=True)
def update_module_file(module):
    from .module_tools import Module

    for module in module:
        Module.get_by_name(module).update_module_file()


@odoo_module.command(name="run-tests")
@pass_config
@click.pass_context
def run_tests(ctx, config):
    started = datetime.now()
    if not config.devmode and not config.force:
        click.secho(
            "Devmode required to run unit tests. Database will be destroyed.", fg="red"
        )
        sys.exit(-1)

    if not config.force:
        click.secho(
            (
                "Please provide parameter -f - database will be dropped. Otherwise "
                "tests are run against existing db. \n\nodoo -f run-tests"
            ),
            fg="yellow",
        )

    from .odoo_config import MANIFEST

    tests = MANIFEST().get("tests", [])
    if not tests:
        click.secho("No test files found!")
        return

    if config.force:
        Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)
        Commands.invoke(ctx, "reset-db")
        Commands.invoke(ctx, "update", "", tests=False, no_dangling_check=True)

    from .module_tools import Module
    from .odoo_config import customs_dir

    success, failed = [], []
    for module in tests:
        module = Module.get_by_name(module)
        testfiles = list(module.get_all_files_of_module())
        testfiles = [x for x in testfiles if str(x).startswith("tests/")]
        testfiles = [x for x in testfiles if str(x).endswith(".py")]
        testfiles = [x for x in testfiles if x.name != "__init__.py"]
        testfiles = [x for x in testfiles if x.name.startswith("test_")]

        # identify test files and run them, otherwise tests of dependent modules are run
        for file in sorted(testfiles):
            mfpath = module.manifest_path.parent
            file = mfpath.relative_to(customs_dir()) / file
            if config.use_docker:
                params = ["odoo", "/odoolib/unit_test.py", f"{file}"]
                click.secho(f"Running test: {file}", fg="yellow", bold=True)
                res = __dcrun(
                    params + ["--log-level=error", "--not-interactive"], returncode=True
                )
                if res:
                    failed.append(file)
                    click.secho(
                        f"Failed, running again with debug on: {file}",
                        fg="red",
                        bold=True,
                    )
                    res = __cmd_interactive(
                        *(["run", "--rm"] + params + ["--log-level=debug"])
                    )
                else:
                    success.append(file)

    elapsed = datetime.now() - started
    click.secho(f"Time: {elapsed}", fg="yellow")

    # in force-mode shut down
    if config.force:
        Commands.invoke(ctx, "down", volumes=True)

    if failed:
        click.secho("Tests failed: ", fg="red")
        for mod in failed:
            click.secho(str(mod), fg="red")
        sys.exit(-1)
    else:
        for mod in success:
            click.secho(str(mod), fg="green")
        click.secho("Tests OK", fg="green")


@odoo_module.command(name="download-openupgrade")
@pass_config
@click.option("--version", help="Destination Version", required=True)
@click.pass_context
def download_openupgrade(ctx, config, version):
    from .odoo_config import customs_dir

    dir_openupgrade = Path(tempfile.mktemp())
    subprocess.check_call(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            version,
            "https://github.com/OCA/OpenUpgrade",
            dir_openupgrade / "openupgrade",
        ]
    )

    if float(version) < 14.0:
        destination_path = "odoo"
    else:
        destination_path = "openupgrade"

    sync_folder(
        dir_openupgrade / "openupgrade",
        customs_dir() / destination_path,
        excludes=[".git"],
    )
    shutil.rmtree(dir_openupgrade)


def _get_outdated_versioned_modules_of_deptree(modules):
    """

    Gets dependency tree of modules and copmares version in manifest with
    version in database. If db is newer then update is required.

    This usually habens after an update of odoo core.

    """
    from .module_tools import Modules, DBModules, Module
    from .odoo_config import MANIFEST

    mods = Modules()

    for module in modules:
        if module == "base":
            continue

        for dep in mods.get_module_flat_dependency_tree(Module.get_by_name(module)):
            meta_info = DBModules.get_meta_data(dep.name)
            if not meta_info:
                continue
            version = meta_info["version"]
            if not version:
                continue
            try:
                version = tuple([int(x) for x in version.split(".")])
            except Exception:
                click.secho(
                    f"Broken version name in module {meta_info}: {version}", fg="red"
                )
                sys.exit(-1)
            new_version = Module.get_by_name(dep).manifest_dict.get("version")
            if not new_version:
                continue
            new_version = tuple([int(x) for x in new_version.split(".")])
            if len(new_version) == 2:
                # add odoo version in front
                new_version = tuple(
                    [int(x) for x in str(MANIFEST()["version"]).split(".")]
                    + list(new_version)
                )

            if new_version > version:
                yield dep


@odoo_module.command()
@click.argument("migration-file", required=True)
@click.argument("mode", required=True)
@click.option("--allow-serie", is_flag=True)
@click.option("--force-version")
@pass_config
@click.pass_context
def marabunta(ctx, config, migration_file, mode, allow_serie, force_version):
    click.secho(
        """
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
    """,
        fg="red",
    )

    click.secho("=================================", fg="yellow")
    click.secho("MARABUNTA", fg="yellow")
    click.secho("=================================", fg="yellow")
    params = [
        "--migration-file",
        "/opt/src/" + migration_file,
        "--database",
        config.dbname,
        "--db-user",
        config.db_user,
        "--db-password",
        config.db_pwd,
        "--db-port",
        config.db_port,
        "--db-host",
        config.db_host,
        "--mode",
        mode,
    ]
    if allow_serie:
        params += ["--allow-serie"]
    if force_version:
        params += ["--force-version", force_version]

    params = ["run", "odoo", "/usr/local/bin/marabunta"] + params
    return __cmd_interactive(*params)


@odoo_module.command(
    help=("If menu items are missing, then recomputing the parent store" "can help")
)
@pass_config
@click.pass_context
def recompute_parent_store(ctx, config):
    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell

    click.secho("Recomputing parent store...", fg="blue")
    lib_shell(
        (
            "for model in self.env['ir.model'].search([]):\n"
            "   try:\n"
            "       obj = self.env[model.model]\n"
            "   except KeyError: pass\n"
            "   else:\n"
            "       obj._parent_store_compute()\n"
            "       env.cr.commit()\n"
        )
    )
    click.secho("Recompute parent store done.", fg="green")


@odoo_module.command(
    help=(
        "As the name says: if db was transferred, web-icons are restored"
        " on missing assets"
    )
)
@pass_config
@click.pass_context
def restore_web_icons(ctx, config):
    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell

    click.secho("Restoring web icons...", fg="blue")
    lib_shell(
        (
            "for x in self.env['ir.ui.menu'].search([]):\n"
            "   if not x.web_icon: continue\n"
            "   x.web_icon_data = x._compute_web_icon_data(x.web_icon)\n"
            "   env.cr.commit()\n"
        )
    )
    click.secho("Restored web icons.", fg="green")


@odoo_module.command()
@click.argument("module", nargs=-1, required=False)
@click.option(
    "--since-git-sha",
    "-i",
    default=None,
    is_flag=False,
    help="Extracts modules changed since this git sha and updates them",
)
@click.option(
    "--installed-modules",
    "-i",
    default=False,
    is_flag=True,
    help="Updates only installed modules",
)
@click.option(
    "--dangling-modules",
    "-d",
    default=False,
    is_flag=True,
    help="Updates only dangling modules",
)
@click.option(
    "--no-update-module-list",
    "-n",
    default=False,
    is_flag=True,
    help="Does not install/update module list module",
)
@click.option(
    "--non-interactive", "-I", default=True, is_flag=True, help="Not interactive"
)
@click.option(
    "--check-install-state",
    default=True,
    is_flag=True,
    help="Check for dangling modules afterwards",
)
@click.option(
    "--no-restart",
    default=False,
    is_flag=True,
    help="If set, no machines are restarted afterwards",
)
@click.option(
    "--no-dangling-check",
    default=False,
    is_flag=True,
    help="Not checking for dangling modules",
)
@click.option("--tests", default=False, is_flag=True, help="Runs tests")
@click.option("--i18n", default=False, is_flag=True, help="Overwrite Translations")
@click.option("--no-install-server-wide-first", default=False, is_flag=True)
@click.option("--no-extra-addons-paths", is_flag=True)
@click.option(
    "-c",
    "--config-file",
    default="config_update",
    help="Specify config file to use, for example config_update",
)
@click.option("--server-wide-modules")
@click.option("--additional-addons-paths")
@click.option(
    "--uninstall", is_flag=True, help="Executes just uninstallation of modules."
)
@pass_config
@click.pass_context
def update(
    ctx,
    config,
    module,
    since_git_sha,
    dangling_modules,
    installed_modules,
    non_interactive,
    no_update_module_list,
    no_install_server_wide_first,
    no_extra_addons_paths,
    no_dangling_check=False,
    check_install_state=True,
    no_restart=True,
    i18n=False,
    tests=False,
    config_file=False,
    server_wide_modules=False,
    additional_addons_paths=False,
    uninstall=False,
):
    """
    Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)
    Minimal downtime;

    To update all (custom) modules set "all" here


    Sample call migration 14.0:
    odoo update --no-dangling-check --config-file=config_migration --server-wide-modules=web,openupgrade_framework --additional-addons-paths=openupgrade base



    """
    param_module = module

    click.secho(
        (
            "Started with parameters: \n"
            f"no_dangling_check: {no_dangling_check}\n"
            f"modules: {module}\n"
        )
    )
    click.secho(
        """

           _                               _       _
          | |                             | |     | |
  ___   __| | ___   ___    _   _ _ __   __| | __ _| |_ ___
 / _ \\ / _` |/ _ \\ / _ \\  | | | | '_ \\ / _` |/ _` | __/ _ \\
| (_) | (_| | (_) | (_) | | |_| | |_) | (_| | (_| | ||  __/
 \\___/ \\__,_|\\___/ \\___/   \\__,_| .__/ \\__,_|\\__,_|\\__\\___|
                                | |
                                |_|
    """,
        fg="green",
    )
    from .module_tools import Modules, DBModules, Module

    # ctx.invoke(module_link)
    if config.run_postgres:
        Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
        Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)

    def _perform_install(module):
        if since_git_sha and module:
            raise Exception("Conflict: since-git-sha and modules")
        if since_git_sha:
            module = list(_get_changed_modules(since_git_sha))

            # filter modules to defined ones in MANIFEST
            click.secho(f"Following modules change since last sha: {' '.join(module)}")
            from .odoo_config import MANIFEST

            module = list(filter(lambda x: x in MANIFEST()["install"], module))
            click.secho(
                (
                    "Following modules change since last sha "
                    f"(filtered to manifest): {' '.join(module)}"
                )
            )

            if not module:
                click.secho("No module update required - exiting.")
                return
        else:
            module = list(
                filter(lambda x: x, sum(map(lambda x: x.split(","), module), []))
            )  # '1,2 3' --> ['1', '2', '3']

        if not module and not since_git_sha:
            module = _get_default_modules_to_update()

        outdated_modules = list(
            map(
                lambda x: x.name,
                set(_get_outdated_versioned_modules_of_deptree(module)),
            )
        )

        if not no_restart:
            if config.use_docker:
                Commands.invoke(ctx, "kill", machines=get_services(config, "odoo_base"))
                if config.run_redis:
                    Commands.invoke(ctx, "up", machines=["redis"], daemon=True)
                if config.run_postgres:
                    Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
                Commands.invoke(ctx, "wait_for_container_postgres")

        def show_dangling():
            dangling = list(DBModules.get_dangling_modules())
            if dangling:
                click.echo("Displaying dangling modules:")
                for row in dangling:
                    click.echo("{}: {}".format(row[0], row[1]))
            return bool(dangling)

        if not no_dangling_check:
            if any(x[1] == "uninstallable" for x in DBModules.get_dangling_modules()):
                for x in DBModules.get_dangling_modules():
                    click.echo("{}: {}".format(*x[:2]))
                if (
                    non_interactive
                    or input(
                        (
                            "Uninstallable modules found - "
                            "shall I set them to 'uninstalled'? [y/N]"
                        )
                    ).lower()
                    == "y"
                ):
                    _execute_sql(
                        config.get_odoo_conn(),
                        (
                            "update ir_module_module set state = "
                            "'uninstalled' where state = 'uninstallable';"
                        ),
                    )
            if DBModules.get_dangling_modules() and not dangling_modules:
                if not no_dangling_check:
                    if show_dangling():
                        input("Abort old upgrade and continue? (Ctrl+c to break)")
                        ctx.invoke(abort_upgrade)
        if installed_modules:
            module += __get_installed_modules(config)
        if dangling_modules:
            module += [x[0] for x in DBModules.get_dangling_modules()]
        module = list(filter(bool, module))
        if not module:
            raise Exception("no modules to update")

        click.echo("Run module update")
        if config.odoo_update_start_notification_touch_file_in_container:
            Path(
                config.odoo_update_start_notification_touch_file_in_container
            ).write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        def _technically_update(modules):
            try:
                modules = list(
                    map(lambda x: x.name if isinstance(x, Module) else x, modules)
                )
                params = [",".join(modules)]
                if no_extra_addons_paths:
                    params += ["--no-extra-addons-paths"]
                if non_interactive:
                    params += ["--non-interactive"]
                if no_install_server_wide_first:
                    params += ["--no-install-server-wide-first"]
                if no_update_module_list:
                    params += ["--no-update-modulelist"]
                if no_dangling_check:
                    params += ["--no-dangling-check"]
                if i18n:
                    params += ["--i18n"]
                if not tests:
                    params += ["--no-tests"]
                if server_wide_modules:
                    params += ["--server-wide-modules", server_wide_modules]
                if additional_addons_paths:
                    params += ["--additional-addons-paths", additional_addons_paths]
                params += ["--config-file=" + config_file]
                rc = _exec_update(config, params)
                if rc:
                    raise UpdateException(module)

            except UpdateException:
                raise
            except Exception as ex:
                click.echo(traceback.format_exc())
                ctx.invoke(show_install_state, suppress_error=no_dangling_check)
                raise Exception(
                    ("Error at /update_modules.py - " "aborting update process.")
                ) from ex

        if outdated_modules:
            _technically_update(outdated_modules)
        _technically_update(module)

        if not no_restart and config.use_docker:
            Commands.invoke(ctx, "restart", machines=["odoo"])
            if config.run_odoocronjobs:
                Commands.invoke(ctx, "restart", machines=["odoo_cronjobs"])
            if config.run_queuejobs:
                Commands.invoke(ctx, "restart", machines=["odoo_queuejobs"])
            Commands.invoke(ctx, "up", daemon=True)

        Commands.invoke(ctx, "status")
        if config.odoo_update_start_notification_touch_file_in_container:
            Path(
                config.odoo_update_start_notification_touch_file_in_container
            ).write_text("0")

    def _uninstall_marked_modules():
        """
        Checks for file "uninstall" in customs root and sets modules to uninstalled.
        """
        from .odoo_config import MANIFEST

        if float(config.odoo_version) < 11.0:
            return
        # check if something is todo
        to_uninstall = MANIFEST().get("uninstall", [])
        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            click.secho(
                "Going to uninstall {}".format(", ".join(to_uninstall)), fg="red"
            )

            if config.use_docker:
                from .lib_control_with_docker import shell as lib_shell
            for module in to_uninstall:
                click.secho(f"Uninstall {module}", fg="red")
                lib_shell(
                    (
                        "self.env['ir.module.module'].search(["
                        f"('name', '=', '{module}'),"
                        "('state', 'in', "
                        "['to upgrade', 'to install', 'installed']"
                        ")]).module_uninstall()\n"
                        "self.env.cr.commit()"
                    )
                )

        to_uninstall = [x for x in to_uninstall if DBModules.is_module_installed(x)]
        if to_uninstall:
            abort(f"Failed to uninstall: {','.join(to_uninstall)}")

    if not uninstall:
        _perform_install(module)
    _uninstall_marked_modules()

    all_modules = (
        not param_module
        or len(param_module) == 1
        and param_module[0] in ["all", "base", False, None, ""]
    )

    # check danglings
    if not no_dangling_check and all_modules:
        ctx.invoke(show_install_state, suppress_error=False)

    if check_install_state:
        if all_modules:
            ctx.invoke(
                show_install_state,
                suppress_error=no_dangling_check,
                missing_as_error=True,
            )
        else:
            missing = list(DBModules.check_if_all_modules_from_install_are_installed())
            problem_missing = set()
            for module in module:
                if module in missing:
                    problem_missing.add(module)
            if problem_missing:
                for missing in sorted(problem_missing):
                    click.secho("Missing: {missing}", fg="red")
                abort("Missing after installation")


@odoo_module.command(name="update-i18n", help="Just update translations")
@click.argument("module", nargs=-1, required=False)
@click.option(
    "--no-restart",
    default=False,
    is_flag=True,
    help="If set, no machines are restarted afterwards",
)
@pass_config
@click.pass_context
def update_i18n(ctx, config, module, no_restart):
    if config.run_postgres:
        Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
    Commands.invoke(ctx, "wait_for_container_postgres")
    module = list(
        filter(lambda x: x, sum(map(lambda x: x.split(","), module), []))
    )  # '1,2 3' --> ['1', '2', '3']

    if not module:
        module = _get_default_modules_to_update()

    try:
        params = [",".join(module)]
        params += ["--non-interactive"]
        params += ["--no-update-modulelist"]
        params += ["--no-dangling-check"]
        params += ["--only-i18n"]
        _exec_update(config, params)
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if not no_restart:
        Commands.invoke(ctx, "restart", machines=["odoo"])


@odoo_module.command()
@pass_config
def progress(config):
    """
    Displays installation progress
    """
    for row in _execute_sql(
        config.get_odoo_conn(),
        "select state, count(*) from ir_module_module group by state;",
        fetchall=True,
    ):
        click.echo("{}: {}".format(row[0], row[1]))


@odoo_module.command(name="show-install-state")
@pass_config
def show_install_state(config, suppress_error=False, missing_as_error=False):
    from .module_tools import DBModules

    dangling = list(DBModules.get_dangling_modules())
    if dangling:
        click.echo("Displaying dangling modules:")
    for row in dangling:
        click.echo("{}: {}".format(row[0], row[1]))

    # get modules, that are not installed:
    missing = list(DBModules.check_if_all_modules_from_install_are_installed())
    for missing_item in missing:
        click.secho((f"Module {missing_item} not installed!"), fg="red")

    if not suppress_error:
        if dangling or (missing_as_error and missing):
            raise Exception(
                (
                    "Dangling modules detected - "
                    " please fix installation problems and retry! \n"
                    f"Dangling: {dangling}\n"
                    f"Missing: {missing}\n"
                )
            )


@odoo_module.command(name="show-addons-paths")
def show_addons_paths():
    from .odoo_config import get_odoo_addons_paths

    paths = get_odoo_addons_paths()
    for path in paths:
        click.echo(path)


@odoo_module.command(name="pretty-print-manifest")
def pretty_print_manifest():
    from .odoo_config import MANIFEST

    MANIFEST().rewrite()


@odoo_module.command(name="show-conflicting-modules")
def show_conflicting_modules():
    from .odoo_config import get_odoo_addons_paths

    get_odoo_addons_paths()


def _exec_update(config, params):
    if config.use_docker:
        params = ["run", "odoo_update", "/update_modules.py"] + params
        return __cmd_interactive(*params)
    else:
        from . import lib_control_native

        return lib_control_native._update_command(config, params)


def _get_available_robottests(ctx, param, incomplete):
    from .robo_helpers import _get_all_robottest_files
    from .odoo_config import customs_dir

    path = customs_dir() or Path(os.getcwd())
    path = path / (Path(os.getcwd()).relative_to(path))
    testfiles = list(map(str, _get_all_robottest_files(path))) or []
    if incomplete:
        if "/" in incomplete:
            testfiles = list(filter(lambda x: str(x).startswith(incomplete), testfiles))
        else:
            testfiles = list(filter(lambda x: incomplete in x, testfiles))
    return sorted(testfiles)


@odoo_module.command()
@click.argument("file", required=False, shell_complete=_get_available_robottests)
@click.option("-u", "--user", default="admin")
@click.option("-a", "--all", is_flag=True)
@click.option("-n", "--test_name", is_flag=False)
@click.option(
    "-p", "--param", multiple=True, help="e.g. --param key1=value1 --param key2=value2"
)
@click.option("--parallel", default=1, help="Parallel runs of robots.")
@click.option(
    "--keep-token-dir",
    is_flag=True,
    help="If set, then the intermediate run directory is kept. Helps to separate test runs of same robot file safely.",
)
@click.option(
    "-t",
    "--tags",
    is_flag=False,
    help=(
        "Tags can be comined with AND OR or just comma separated; "
        "may include wilcards and some regex expressions"
    ),
)
@click.option(
    "-j",
    "--output-json",
    is_flag=True,
    help=("If set, then a json is printed to console, with detailed informations"),
)
@click.option(
    "--results-file", help="concrete filename where the results.json is stored"
)
@pass_config
@click.pass_context
def robotest(
    ctx,
    config,
    file,
    user,
    all,
    tags,
    test_name,
    param,
    parallel,
    output_json,
    keep_token_dir,
    results_file,
):
    PARAM = param
    del param
    started = arrow.utcnow()

    from pathlib import Path
    from .odoo_config import customs_dir
    from .module_tools import DBModules

    if not config.devmode and not config.force:
        click.secho(
            ("Devmode required to run unit tests. Database will be destroyed."),
            fg="red",
        )
        sys.exit(-1)

    from .robo_helpers import _select_robot_filename

    filenames = _select_robot_filename(file, run_all=all)
    del file

    if not filenames:
        return

    click.secho("\n".join(map(str, filenames)), fg="green", bold=True)

    from .robo_helpers import get_odoo_modules

    os.chdir(customs_dir())
    odoo_modules = set(get_odoo_modules(config.verbose, filenames, customs_dir()))
    odoo_modules = list(odoo_modules | set(["web_selenium", "robot_utils"]))

    if odoo_modules:

        def not_installed(module):
            return DBModules.get_meta_data(module)["state"] == "uninstalled"

        modules_to_install = list(filter(not_installed, odoo_modules))
        if modules_to_install:
            click.secho(
                (
                    "Installing required modules for robot tests: "
                    f"{','.join(modules_to_install)}"
                ),
                fg="yellow",
            )
            Commands.invoke(
                ctx, "update", module=modules_to_install, no_dangling_check=True
            )

    pwd = config.DEFAULT_DEV_PASSWORD
    if pwd == "True" or pwd is True:
        pwd = "1"

    def params():
        params = {
            "url": "http://proxy",
            "user": user,
            "dbname": config.DBNAME,
            "password": pwd,
            "selenium_timeout": 20,  # selenium timeout,
            "parallel": parallel,
        }
        if test_name:
            params["test_name"] = test_name
        if tags:
            params["tags"] = tags

        for param in PARAM:
            k, v = param.split("=")
            params[k] = v
            del param

        return params

    token = str(uuid.uuid4())
    data = json.dumps(
        {
            "test_files": list(map(str, filenames)),
            "token": token,
            "results_file": results_file or "",
            "params": params(),
        }
    )
    data = base64.b64encode(data.encode("utf-8"))

    params = [
        "robot",
    ]

    workingdir = customs_dir() / (Path(os.getcwd()).relative_to(customs_dir()))
    os.chdir(workingdir)

    __dcrun(params, pass_stdin=data.decode("utf-8"), interactive=True)

    output_path = config.HOST_RUN_DIR / "odoo_outdir" / "robot_output"
    from .robo_helpers import _eval_robot_output

    _eval_robot_output(
        config,
     output_path,
  started,
    output_json,
      token,
   rm_tokendir=not keep_token_dir,
        results_file=results_file,
    )


def _get_unittests_from_module(module_name):
    from .module_tools import Module
    from .odoo_config import MANIFEST_FILE

    testfiles = []
    module = Module.get_by_name(module_name)
    for _file in module.path.glob("tests/test*.py"):
        testfiles.append(_file)
    return testfiles


def _get_unittests_from_modules(module_names):
    testfiles = []
    for module in module_names:
        testfiles += _get_unittests_from_module(module)
    return testfiles


def _get_all_unittest_files(config):
    from .odoo_config import MANIFEST
    from .module_tools import Modules

    modules = Modules().get_all_modules_installed_by_manifest()
    return _get_unittests_from_modules(modules)


@odoo_module.command()
@pass_config
def list_unit_test_files(config):
    files = _get_all_unittest_files(config)
    click.secho("!!!")
    for file in files:
        click.secho(file)
    click.secho("!!!")


@odoo_module.command()
@pass_config
def list_robot_test_files(config):
    from .robo_helpers import _get_all_robottest_files

    files = _get_all_robottest_files()
    click.secho("!!!")
    for file in files:
        click.secho(file)
    click.secho("!!!")


@odoo_module.command()
@click.argument("file", required=False)
@click.option("-w", "--wait-for-remote", is_flag=True)
@click.option("-r", "--remote-debug", is_flag=True)
@click.option("-n", "--non-interactive", is_flag=True)
@click.option("-t", "--tags", is_flag=True)
@click.option("--output-json", is_flag=True)
@pass_config
def unittest(
    config, file, remote_debug, wait_for_remote, non_interactive, output_json, tags
):
    """
    Collects unittest files and offers to run
    """
    from .odoo_config import MANIFEST, MANIFEST_FILE, customs_dir
    from .module_tools import Module
    from pathlib import Path

    if file and "/" not in file:
        try:
            module = Module.get_by_name(file)
        except Exception:
            pass
        else:
            tests = module.path.glob("tests/test*")
            file = ",".join(map(lambda x: str(x), tests))

    todo = []
    if file:
        for file in file.split(","):
            todo.append(file)
    else:
        testfiles = list(sorted(_get_all_unittest_files(config)))
        message = "Please choose the unittest to run."
        filename = inquirer.prompt(
            [inquirer.List("filename", message, choices=testfiles)]
        ).get("filename")
        todo.append(filename)

    if not todo:
        return

    for todoitem in todo:
        click.secho(str(todoitem), fg="green", bold=True)

    def filepath_to_container(filepath):
        return Path("/opt/src/") / filepath

    container_files = list(map(filepath_to_container, todo))

    interactive = True  # means pudb trace turned on
    params = [
        "odoo",
        "/odoolib/unit_test.py",
        f'{",".join(map(str, container_files))}',
    ]
    if wait_for_remote:
        remote_debug = True
        interactive = False

    if non_interactive:
        interactive = False
    del non_interactive

    if remote_debug:
        params += ["--remote-debug"]
    if wait_for_remote:
        params += ["--wait-for-remote"]
    if not interactive:
        params += ["--not-interactive"]

    results_filename = next(tempfile._get_candidate_names())
    params += ["--resultsfile", f"/opt/out_dir/{results_filename}"]

    try:
        __dcrun(params + ["--log-level=debug"], interactive=interactive)
    except subprocess.CalledProcessError:
        pass

    output_path = config.HOST_RUN_DIR / "odoo_outdir" / results_filename
    if not output_path.exists():
        abort("No testoutput generated - seems to be a technical problem.")
    test_result = json.loads(output_path.read_text())
    output_path.unlink()
    passed = [x for x in test_result if not x["rc"]]
    errors = [x for x in test_result if x["rc"]]
    if output_json:
        click.secho("---")
        click.secho(json.dumps(test_result, indent=4))
    else:
        from tabulate import tabulate

        if passed:
            click.secho(
                tabulate(passed, headers="keys", tablefmt="fancy_grid"), fg="green"
            )
        if errors:
            click.secho(
                tabulate(errors, headers="keys", tablefmt="fancy_grid"), fg="red"
            )
    if errors:
        sys.exit(-1)


@odoo_module.command()
@click.argument("name", required=True)
@click.option("-Q", "--quick", is_flag=True)
@pass_config
@click.pass_context
def set_ribbon(ctx, config, name, quick):
    if not quick:
        SQL = """
            Select state from ir_module_module where name = 'web_environment_ribbon';
        """
        res = _execute_sql(config.get_odoo_conn(), SQL, fetchone=True)
        if not (res and res[0] == "installed"):
            Commands.invoke(
                ctx, "update", module=["web_environment_ribbon"], no_dangling_check=True
            )

    _execute_sql(
        config.get_odoo_conn(),
        """
        UPDATE
            ir_config_parameter
        SET
            value = %s
        WHERE
            key = 'ribbon.name';
    """,
        params=(name,),
    )


@odoo_module.command(help="For directly installed odoos.")
@pass_config
@click.pass_context
def generate_update_command(ctx, config):
    modules = _get_default_modules_to_update()
    click.secho(f"-u {','.join(modules)}")


def _get_changed_files(git_sha):
    from .module_tools import Module
    from .tools import git_diff_files

    cwd = os.getcwd()
    filepaths = git_diff_files(cwd, git_sha, "HEAD")
    repo = Repo(cwd)

    # check if there are submodules:
    filepaths2 = []
    cwd = Path(os.getcwd())
    for filepath in filepaths:
        os.chdir(cwd)
        submodule = [x for x in repo.submodules if x.path == filepath]
        if submodule:
            current_commit = str(repo.active_branch.commit)
            old_commit = (
                subprocess.check_output(["git", "rev-parse", f"{git_sha}:./{filepath}"])
                .decode("utf-8")
                .strip()
            )
            new_commit = (
                subprocess.check_output(
                    ["git", "rev-parse", f"{current_commit}:./{filepath}"]
                )
                .decode("utf-8")
                .strip()
            )
            # now diff the submodule
            submodule_path = cwd / filepath
            submodule_relative_path = filepath
            for filepath2 in git_diff_files(submodule_path, old_commit, new_commit):
                filepaths2.append(submodule_relative_path + "/" + filepath2)
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
@click.option("-s", "--start")
@click.pass_context
@pass_config
def list_changed_modules(ctx, config, start):
    modules = _get_changed_modules(start)

    click.secho("---")
    for module in modules:
        click.secho(module)


@odoo_module.command(name="list-changed-files")
@click.option("-s", "--start")
@click.pass_context
@pass_config
def list_changed_files(ctx, config, start):
    files = _get_changed_files(start)

    click.secho("---")
    for file in files:
        click.secho(file)


@odoo_module.command()
@click.option("--on-need", is_flag=True)
@pass_config
@click.pass_context
def make_dir_hashes(ctx, config, on_need):
    from tqdm import tqdm
    from .odoo_config import customs_dir
    from .consts import FILE_DIRHASHES

    customs_dir = customs_dir()
    file_dirhashes = Path(customs_dir) / FILE_DIRHASHES
    if on_need and file_dirhashes.exists():
        return

    if not config.force:
        raise Exception(
            "Needs force option, because I call git clean -xdff and "
            "all your work is lost. (Stashing before)"
        )
    subprocess.check_call(["git", "stash", "--include-untracked"])
    subprocess.check_call(["git", "clean", "-xdff"], cwd=customs_dir)
    hashes = subprocess.check_output(
        ["sha1deep", "-r", "-l", "-j", "5", customs_dir], encoding="utf8"
    ).strip()

    file_hashes = {}
    customs_dir = str(customs_dir)
    for hash in hashes.splitlines():
        hash, file = hash.split(" ", 1)
        file = file.strip()
        if file.startswith("./"):
            file = file[2:]
        elif file.startswith(customs_dir):
            file = file[len(customs_dir) + 1 :]

        file_hashes[file] = hash

    paths = []
    path_hashes = {}
    for path in Path(customs_dir).glob("**/*"):
        if path.is_dir():
            if not (path / "__manifest__.py").exists() and path.name != "odoo":
                continue
            paths.append(path)
    for path in tqdm(paths):
        relpath = str(path.relative_to(customs_dir))
        files = list(
            sorted(filter(lambda x: str(x).startswith(relpath), file_hashes.keys()))
        )
        hashstring = "".join(file_hashes[file] for file in files)
        path_hashes[relpath] = get_hash(hashstring)

    content = json.dumps(path_hashes, indent=4)
    __concurrent_safe_write_file(file_dirhashes, content)
    if config.OWNER_UID:
        os.chown(file_dirhashes, int(config.OWNER_UID), -1)
    return content


@odoo_module.command()
@click.argument("module", required=True)
@click.option("-N", "--no-cache", is_flag=True)
@pass_config
@click.pass_context
def list_deps(ctx, config, module, no_cache):
    import arrow

    started = arrow.get()
    from .module_tools import Modules, DBModules, Module
    from .odoo_config import customs_dir
    from .consts import FILE_DIRHASHES

    modules = Modules()
    module = Module.get_by_name(module)
    # fast lane for base
    if module.name in ["base"]:
        dir_hashes = {}
    else:
        ctx.invoke(make_dir_hashes, on_need=not no_cache)
        dir_hashes = json.loads((customs_dir() / FILE_DIRHASHES).read_text())

    data = {"modules": []}
    data["modules"] = sorted(
        map(lambda x: x.name, modules.get_module_flat_dependency_tree(module))
    )
    data["modules"].append(module.name)

    data["auto_install"] = sorted(
        map(
            lambda x: x.name,
            modules.get_filtered_auto_install_modules_based_on_module_list(
                data["modules"]
            ),
        )
    )
    part1 = arrow.get() - started
    started = arrow.get()
    if config.verbose:
        print(f"part1: {part1.total_seconds()}")

    # get some hashes:
    paths = []
    for path in ["odoo"]:
        paths.append(Path(path))
    for mod in data["modules"]:
        paths.append(Module.get_by_name(mod).path)
    for mod in data["auto_install"]:
        paths.append(Module.get_by_name(mod).path)

    # hash python version
    python_version = config.ODOO_PYTHON_VERSION
    to_hash = str(python_version) + ";"
    for path in list(sorted(set(paths))):
        if config.verbose:
            click.secho(f"Hashing path: {path}")
        _hash = dir_hashes.get(str(path))
        if _hash is None:
            _hash = get_directory_hash(path)
        to_hash += f"{path} {_hash},"

    if config.verbose:
        click.secho(f"\n\nTo Hash:\n{to_hash}\n\n")
    hash = get_hash(to_hash)
    data["hash"] = hash
    part2 = arrow.get() - started
    if config.verbose:
        print(f"part2: {part2.total_seconds()}")

    click.secho("---")
    click.secho(json.dumps(data, indent=4))


@odoo_module.command()
def migrate():
    click.secho(
        (
            "To migrate odoo 14.0 to 15.0 you would do:\n\n"
            "  * odoo download-openupgrade\n"
            "  * change gimera.yml to point to odoo 15 (and other modules)\n"
            "  * change version in MANIFEST to version 15\n"
            "  * gimera apply --update \n"
            "  * odoo update --config-file config_migration\n"
            "\n"
        ),
        fg="green",
    )


Commands.register(progress)
Commands.register(update)
Commands.register(show_install_state)
Commands.register(make_dir_hashes)
