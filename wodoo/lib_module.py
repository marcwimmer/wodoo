from multiprocessing.dummy import Process
import time
import re
import sys
import uuid
import arrow
import threading
import json
import base64
import subprocess
import inquirer
import traceback
from datetime import datetime
import shutil
import os
import tempfile
import click

from wodoo.robo_helpers import _get_required_odoo_modules_from_robot_file
from .tools import is_git_clean
from gimera.repo import Repo
from .tools import get_hash
from .tools import get_directory_hash
from .tools import sync_folder
from .tools import __dcrun
from .tools import __cmd_interactive
from .tools import __get_installed_modules
from .tools import __concurrent_safe_write_file
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import _execute_sql
from .tools import get_services
from .tools import __try_to_set_owner
from .tools import measure_time, abort
from .tools import _update_setting
from .tools import _get_setting
from .tools import get_git_hash
from .module_tools import _determine_affected_modules_for_ir_field_and_related
from pathlib import Path

DTF = "%Y-%m-%d %H:%M:%S"
KEY_SHA_REVISION = "sha.revision"


class UpdateException(Exception):
    pass


class RepeatUpdate(Exception):
    def __init__(self, affected_modules):
        super().__init__(str(affected_modules))
        self.affected_modules = affected_modules


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
        Module.get_by_name(module, nocache=True).update_module_file()


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
                    config,
                    params + ["--log-level=error", "--not-interactive"],
                    returncode=True,
                )
                if res:
                    failed.append(file)
                    click.secho(
                        f"Failed, running again with debug on: {file}",
                        fg="red",
                        bold=True,
                    )
                    res = __cmd_interactive(
                        config, *(["run", "--rm"] + params + ["--log-level=debug"])
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
    from .module_tools import NotInAddonsPath
    from .odoo_config import MANIFEST

    mods = Modules()
    cache_db_modules = {}

    for module in sorted(modules):
        if module == "base":
            continue

        try:
            mod = Module.get_by_name(module)
        except (KeyError, NotInAddonsPath):
            click.secho(
                f"Warning module not found: {module}",
                fg="yellow",
            )
            continue
        for dep in mods.get_module_flat_dependency_tree(mod):
            if dep.name not in cache_db_modules:
                cache_db_modules[dep.name] = DBModules.get_meta_data(dep.name)
            meta_info = cache_db_modules[dep.name]
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
                odoo_version = str(MANIFEST()["version"]).split(".")
                assert (
                    len(odoo_version) == 2
                ), f"Version in manifest should be like 16.0 not '{odoo_version}' as it is in {MANIFEST().path}"
                new_version = tuple(list(map(int, odoo_version)) + list(new_version))
                del odoo_version

            if new_version > version:
                # seen: if version in manifest is 14.0.1.0 and installed in
                # 13.0 odoo then version becomes inside odoo: 13.0.14.0.10
                # so try to match including current version:
                odoo_version = list(map(int, str(MANIFEST()['version']).split(".")))
                new_version = tuple(odoo_version + list(new_version))
                if new_version != version:
                    yield dep


def _get_available_modules(ctx, param, incomplete):
    from .odoo_config import MANIFEST

    try:
        manifest = MANIFEST()
        if not manifest:
            raise Exception("no manifest")
    except:
        return []
    modules = manifest["install"]
    if incomplete:
        modules = [x for x in modules if incomplete in x]
    return sorted(modules)


@odoo_module.command(name="UPDATE")
@click.option(
    "--no-dangling-check",
    default=False,
    is_flag=True,
    help="Not checking for dangling modules",
)
@click.option("--non-interactive", "-I", is_flag=True, help="Not interactive")
@click.option(
    "--recover-view-error",
    is_flag=True,
    help="Can happen if per update fields are removed and views still referencing this field.",
)
@click.option("--i18n", default=False, is_flag=True, help="Overwrite Translations")
@pass_config
@click.pass_context
def update2(ctx, config, no_dangling_check, non_interactive, recover_view_error, i18n):
    conn = config.get_odoo_conn()
    revision = _get_setting(conn, KEY_SHA_REVISION)
    Commands.invoke(
        ctx,
        "update",
        no_outdated_modules=True,
        since_git_sha=revision,
        no_dangling_check=no_dangling_check,
        non_interactive=non_interactive,
        recover_view_error=recover_view_error,
        i18n=i18n,
    )


@odoo_module.command()
@click.argument(
    "module", nargs=-1, required=False, shell_complete=_get_available_modules
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
@click.option("--non-interactive", "-I", is_flag=True, help="Not interactive")
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
@click.option(
    "--test-tags",
    help="e.g. at_install/account_accountant,post_install/account_accountant",
)
@click.option(
    "-l",
    "--log",
    default="info",
    type=click.Choice(["test", "info", "debug", "error"]),
    help="display logs with given level",
)
@click.option(
    "-dt",
    "--default-test-tags",
    is_flag=True,
    help="Adds at_install/{module},post_install/{module},standard/{module}",
)
@click.option(
    "--recover-view-error",
    is_flag=True,
    help="Can happen if per update fields are removed and views still referencing this field.",
)
@click.option(
    "-O",
    "--no-outdated-modules",
    is_flag=True,
    help="dont check for outdated modules (for migrations suitable)",
)
@click.option(
    "--since-git-sha",
    "-G",
    default=None,
    is_flag=False,
    help="Extracts modules changed since this git sha and updates them",
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
    test_tags=False,
    default_test_tags=False,
    config_file=False,
    server_wide_modules=False,
    additional_addons_paths=False,
    uninstall=False,
    log=False,
    recover_view_error=False,
    no_outdated_modules=False,
):
    """
    Just custom modules are updated, never the base modules (e.g. prohibits adding old stock-locations)
    Minimal downtime;

    To update all (custom) modules set "all" here


    Sample call migration 14.0:
    odoo update --no-dangling-check --config-file=config_migration --server-wide-modules=web,openupgrade_framework --additional-addons-paths=openupgrade base



    """

    param_module = module

    if recover_view_error and not non_interactive:
        abort(
            "Recover view error requires non interactive execution (stdout parse required)"
        )

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
    from .odoo_config import MANIFEST

    if test_tags and default_test_tags:
        abort("Conflict: parameter test-tags and default-test-tags")

    if config.run_postgres:
        Commands.invoke(ctx, "up", machines=["postgres"], daemon=True)
        Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)

    def _perform_install(module):
        if since_git_sha and module:
            raise Exception("Conflict: since-git-sha and modules")
        if since_git_sha:
            module = _get_modules_since_git_sha(since_git_sha)

            if not module:
                click.secho("No module update required - exiting.")
                return
        else:
            module = _parse_modules(module)

        if not module and not since_git_sha:
            module = _get_default_modules_to_update()

        def _get_outdated_modules():
            return list(
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

        if not no_dangling_check:
            _do_dangling_check(ctx, config, dangling_modules, non_interactive)
        if installed_modules:
            module += __get_installed_modules(config)
        if dangling_modules:
            module += [x[0] for x in DBModules.get_dangling_modules()]
        module = list(filter(bool, module))
        if not module:
            raise Exception("no modules to update")

        def _effective_test_tags():
            if default_test_tags:
                return ",".join(
                    f"at_install/{x},post_install{x},standard/{x}" for x in module
                )
            else:
                return test_tags or ""

        click.echo("Run module update")
        if config.odoo_update_start_notification_touch_file_in_container:
            Path(
                config.odoo_update_start_notification_touch_file_in_container
            ).write_text(datetime.now().strftime(DTF))

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
                if _effective_test_tags():
                    params += ["--test-tags=" + _effective_test_tags()]
                if server_wide_modules:
                    params += ["--server-wide-modules", server_wide_modules]
                if additional_addons_paths:
                    params += ["--additional-addons-paths", additional_addons_paths]
                if log:
                    params += [f"--log={log}"]
                params += ["--config-file=" + config_file]
                rc = list(_exec_update(config, params, non_interactive=non_interactive))
                if len(rc) == 1:
                    rc = rc[0]
                else:
                    rc, output = rc

                if rc:
                    if recover_view_error:
                        try:
                            _try_to_recover_view_error(config, output)
                        except RepeatUpdate as ex:
                            _technically_update(ex.affected_modules)
                        except Exception as ex:
                            raise UpdateException(module) from ex
                        else:
                            raise Exception(f"Error at update - please check logs")
                    else:
                        raise UpdateException(module)

            except UpdateException:
                raise
            except RepeatUpdate:
                raise
            except Exception as ex:
                click.echo(traceback.format_exc())
                ctx.invoke(show_install_state, suppress_error=no_dangling_check)
                raise Exception(
                    ("Error at /update_modules.py - " "aborting update process.")
                ) from ex

        trycount = 0
        max_try_count = 5
        while True:
            trycount += 1
            try:
                if not no_outdated_modules:
                    outdated_modules = _get_outdated_modules()
                    if outdated_modules:
                        click.secho(
                            f"Outdated modules: {','.join(outdated_modules)}",
                            fg="yellow",
                        )
                        _technically_update(outdated_modules)
                _technically_update(module)
            except RepeatUpdate:
                click.secho("Retrying update.")
                if trycount >= max_try_count:
                    raise
            else:
                break

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

    if not uninstall:
        _perform_install(module)

    all_modules = (
        not param_module
        or len(param_module) == 1
        and param_module[0] in ["all", "base", False, None, ""]
    )

    if uninstall or all_modules:
        _uninstall_marked_modules(config, MANIFEST().get("uninstall", []))

    # check danglings
    if not no_dangling_check and all_modules:
        ctx.invoke(show_install_state, suppress_error=False)

    if check_install_state:
        _do_check_install_state(ctx, config, module, all_modules, no_dangling_check)

    _set_sha(config)


def _set_sha(config):
    conn = config.get_odoo_conn()
    try:
        sha = get_git_hash()
    except:
        pass
    else:
        _update_setting(conn, KEY_SHA_REVISION, sha)


def _try_to_recover_view_error(config, output):
    """
    If a field is removed it can be that views still reference it, so
    remove the item from the view.

    Field "product_not_show_ax_code" does not exist in model "res.company"

    Field "dummy1" does not exist in model "res.partner"

    View error context:
    {'file': '/opt/src/odoo/addons/module_respartner_dummyfield2/partnerview.xml',
    'line': 3,
    'name': 'res.partner form',
    'view': ir.ui.view(545,),
    'view.model': 'res.partner',
    'view.parent': ir.ui.view(128,),
    'xmlid': 'view_res_partner_form'}

    Caution: this view is just the one that updates; the conflicting view is not listed.
    Just a select statement is created by the other view.
    """
    lines = output.splitlines()

    for i, line in enumerate(lines):
        match = re.findall('Field "([^"]*?)" does not exist in model "([^"]*?)"', line)
        if match:
            field, model = match[0]
            affected_modules = _determine_affected_modules_for_ir_field_and_related(
                config, field, model
            )
            raise RepeatUpdate(affected_modules)


def show_dangling():
    from .module_tools import Modules, DBModules, Module

    dangling = list(DBModules.get_dangling_modules())
    if dangling:
        click.echo("Displaying dangling modules:")
        for row in dangling:
            click.echo("{}: {}".format(row[0], row[1]))
    return bool(dangling)


def _do_check_install_state(ctx, config, module, all_modules, no_dangling_check):
    from .module_tools import Modules, DBModules, Module

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
                click.secho(f"Missing: {missing}", fg="red")
            abort("Missing after installation")


def _do_dangling_check(ctx, config, dangling_modules, non_interactive):
    from .module_tools import Modules, DBModules, Module

    if any(x[1] == "uninstallable" for x in DBModules.get_dangling_modules()):
        if non_interactive:
            abort("Danling modules exist. Provide --no-dangling-check otherwise.")
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
        if show_dangling() and not non_interactive:
            input("Abort old upgrade and continue? (Ctrl+c to break)")
            ctx.invoke(abort_upgrade)


def _parse_modules(modules):
    if isinstance(modules, (str, bytes)):
        modules = modules.split(",")
    modules = list(
        filter(lambda x: x, sum(map(lambda x: x.split(","), modules), []))
    )  # '1,2 3' --> ['1', '2', '3']
    return modules


@odoo_module.command()
@click.argument("modules", nargs=-1, required=False)
@pass_config
@click.pass_context
def uninstall(ctx, config, modules):
    modules = _parse_modules(modules)
    _uninstall_marked_modules(config, modules)


def _uninstall_marked_modules(config, modules):
    """
    Checks for file "uninstall" in customs root and sets modules to uninstalled.
    """
    from .module_tools import Modules, DBModules, Module

    assert not isinstance(modules, str)

    if not modules:
        return

    if float(config.odoo_version) < 11.0:
        return
    modules = [x for x in modules if DBModules.is_module_installed(x)]
    if not modules:
        return
    click.secho(f"Going to uninstall {','.join(modules)}", fg="red")

    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell

    for module in modules:
        click.secho(f"Uninstall {module}", fg="red")
        lib_shell(
            config,
            (
                "self.env['ir.module.module'].search(["
                f"('name', '=', '{module}'),"
                "('state', 'in', "
                "['to upgrade', 'to install', 'installed']"
                ")]).module_uninstall()\n"
                "self.env.cr.commit()"
            ),
        )
        del module

    modules = [x for x in modules if DBModules.is_module_installed(x)]
    if modules:
        abort(f"Failed to uninstall: {','.join(modules)}")


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
        retcode = next(_exec_update(config, params, non_interactive=True))
        if retcode:
            raise Exception("Error at update i18n happened.")
    except Exception:
        click.echo(traceback.format_exc())
        ctx.invoke(show_install_state, suppress_error=True)
        raise Exception("Error at /update_modules.py - aborting update process.")

    if not no_restart:
        Commands.invoke(ctx, "restart", machines=["odoo"])


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
            abort(
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


@odoo_module.command(name="show-conflicting-modules")
def show_conflicting_modules():
    from .odoo_config import get_odoo_addons_paths

    get_odoo_addons_paths()


def _exec_update(config, params, non_interactive=False):
    params = ["odoo_update", "/update_modules.py"] + params
    if not non_interactive:
        yield __cmd_interactive(
            config,
            *(
                [
                    "run",
                    "--rm",
                ]
                + params
            ),
        )
    else:
        try:
            returncode, output = __dcrun(config, list(params), returnproc=True)
            yield returncode
            yield output
        except subprocess.CalledProcessError as ex:
            yield ex.returncode


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
            data = DBModules.get_meta_data(module)
            if not data:
                abort(f"Could not get state for {module}")
            return data["state"] == "uninstalled"

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

    token = arrow.get().strftime("%Y-%m-%d_%H%M%S_") + str(uuid.uuid4())
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

    __dcrun(config, params, pass_stdin=data.decode("utf-8"), interactive=True)

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
@click.option("--log", is_flag=True)
@pass_config
def unittest(
    config, file, remote_debug, wait_for_remote, non_interactive, output_json, tags, log
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

            # walk to root - otherwise the files are not found
            os.chdir(customs_dir())
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
    if log:
        params += ["--log-level=debug"]
    else:
        params += ["--log-level=info"]

    try:
        __dcrun(config, params, interactive=interactive)
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
        filepath = repo.path / filepath
        os.chdir(cwd)

        def get_submodule(filepath):
            for submodule in repo.get_submodules():
                try:
                    filepath.relative_to(submodule.path)
                    return submodule
                except ValueError:
                    continue

        submodule = get_submodule(filepath)

        if submodule:
            current_commit = str(repo.hex)
            relpath = filepath.relative_to(repo.path)
            old_commit = (
                subprocess.check_output(
                    [
                        "git",
                        "rev-parse",
                        f"{git_sha}:./{relpath}",
                    ], encoding='utf8'
                )
                .strip()
            )
            new_commit = (
                subprocess.check_output(
                    ["git", "rev-parse", f"{current_commit}:./{relpath}"], encoding='utf8',
                )
                .strip()
            )
            # now diff the submodule
            for filepath2 in git_diff_files(filepath, old_commit, new_commit):
                filepaths2.append(str(relpath / filepath2))
        else:
            filepaths2.append(str(filepath.relative_to(repo.path)))

    return filepaths2


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


def _get_global_hash_paths(relative_to_customs_dir=False):
    from .odoo_config import customs_dir

    customs_dir_path = customs_dir()
    odoo_path = customs_dir_path / "odoo"
    global_hash_paths = [
        odoo_path / "odoo",
        odoo_path / "requirements.txt",
        odoo_path / "odoo-bin",
    ]
    if not relative_to_customs_dir:
        return global_hash_paths
    return [p.relative_to(customs_dir_path) for p in global_hash_paths]


def _clean_customs(ctx, config):
    from .odoo_config import customs_dir

    path = customs_dir()
    if not config.force:
        abort(
            "Needs force option, because I call git clean -xdff and "
            "all your work is lost. (Stashing before)"
        )
    if not is_git_clean(path):
        subprocess.check_call(["git", "stash", "--include-untracked"], cwd=path)
    subprocess.check_call(["git", "clean", "-xdff"], cwd=path)


hash_cache = {}


def _get_directory_hash(path):
    if path not in hash_cache:
        hash_cache[path] = get_directory_hash(path)
    return hash_cache[path]


@odoo_module.command()
@click.argument("module", required=True)
@click.option("-N", "--no-cache", is_flag=True)
@pass_config
@click.pass_context
def list_deps(ctx, config, module, no_cache):
    import arrow

    started = arrow.get()
    from .module_tools import Modules, DBModules, Module
    from .module_tools import NotInAddonsPath
    from .odoo_config import customs_dir
    from .consts import FILE_DIRHASHES

    _clean_customs(ctx, config)

    click.secho("Loading Modules...", fg="yellow")
    modules = Modules()
    if module == "all":
        do_all = True
        module = [Module.get_by_name(x) for x in modules.modules]
    else:
        do_all = False
        module = [Module.get_by_name(module)]

    result = {}
    for module in module:
        data = {"modules": []}
        data["modules"] = sorted(
            list(map(lambda x: x.name, modules.get_module_flat_dependency_tree(module)))
            + [module.name]
        )

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
        paths = _get_global_hash_paths(True)
        for mod in data["modules"]:
            try:
                objmod = Module.get_by_name(mod)
                paths.append(objmod.path)
            except NotInAddonsPath:
                pass
        for mod in data["auto_install"]:
            paths.append(Module.get_by_name(mod).path)

        # hash python version
        python_version = config.ODOO_PYTHON_VERSION
        to_hash = str(python_version) + ";"
        for path in list(sorted(set(paths))):
            _hash = _get_directory_hash(path)
            if _hash is None:
                raise Exception(
                    f"No hash found for {path} try it again with --no-cache"
                )
            to_hash += f"{path} {_hash},"

        if config.verbose:
            # break the hash in chunks and output the hash
            todo = to_hash
            i = 0
            while todo:
                i += 1
                SIZE = 100
                part = todo[:SIZE]
                todo = todo[SIZE:]
                click.secho(f"{i}.\n{part}", fg="blue")
                click.secho(get_hash(part), fg="yellow")

            click.secho(f"\n\nTo Hash:\n{to_hash}\n\n")
        hash = get_hash(to_hash)
        data["hash"] = hash
        part2 = arrow.get() - started
        if config.verbose:
            print(f"part2: {part2.total_seconds()}")

        if not do_all:
            result = data
        else:
            result[module.name] = data

    click.secho("---")
    click.secho(json.dumps(result, indent=4))


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


@odoo_module.command()
@pass_config
@click.pass_context
def list_modules(ctx, config):
    from .module_tools import Modules, DBModules

    mods = Modules()
    modules = list(sorted(mods.get_all_modules_installed_by_manifest()))
    print("---")
    for m in modules:
        print(m)


@odoo_module.command()
@pass_config
@click.pass_context
def list_outdated_modules(ctx, config):
    modules = _get_default_modules_to_update()

    def _get_outdated_modules(module):
        return list(
            map(
                lambda x: x.name,
                set(_get_outdated_versioned_modules_of_deptree(module)),
            )
        )

    print("---")
    for mod2 in _get_outdated_modules(modules):
        print(mod2)


def _get_modules_since_git_sha(sha):
    from .odoo_config import MANIFEST

    module = list(_get_changed_modules(sha))

    # filter modules to defined ones in MANIFEST
    click.secho(f"Following modules change since last sha: {' '.join(module)}")

    module = list(filter(lambda x: x in MANIFEST()["install"], module))
    click.secho(
        (
            "Following modules changed since last sha "
            f"(filtered to manifest): {' '.join(module)}"
        )
    )
    return module


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


@odoo_module.command
@click.option("-f", "--fix-not-in-manifest", is_flag=True)
@click.option("--only-customs", is_flag=True)
@pass_config
def list_installed_modules(config, fix_not_in_manifest, only_customs):
    from .module_tools import DBModules, Module
    from .module_tools import NotInAddonsPath
    from .odoo_config import customs_dir
    from .odoo_config import MANIFEST

    collected = []
    not_in_manifest = []
    manifest = MANIFEST()
    setinstall = manifest.get("install", [])

    for module in sorted(DBModules.get_all_installed_modules()):
        try:
            mod = Module.get_by_name(module)
        except (Module.IsNot, NotInAddonsPath):
            click.secho(f"Ignoring {module} - not found in source", fg="yellow")
            continue
        if only_customs:
            try:
                parts = mod.path.parts
            except Module.IsNot:
                click.secho(f"Ignoring {module} - not found in source", fg="yellow")
                continue
            if any(x in parts for x in ["odoo", "enterprise", "themes"]):
                continue
        try:
            click.secho(f"{module}: {mod.path}", fg="green")
            if not [x for x in setinstall if x == module]:
                not_in_manifest.append(module)
        except KeyError:
            collected.append(module)

    for module in not_in_manifest:
        if fix_not_in_manifest:
            setinstall += [module]
            click.secho(f"Added to manifest: {module}", fg="green")
        else:
            click.secho(f"Not in MANIFEST: {module}", fg="yellow")
    for module in collected:
        click.secho(f"Not in filesystem: {module}", fg="red")

    if fix_not_in_manifest:
        manifest["install"] = setinstall
        manifest.rewrite()


Commands.register(update)
Commands.register(show_install_state)
