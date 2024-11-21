import random
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
import glob

from .odoo_config import current_version
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
from .tools import table_exists
from .tools import get_services
from .tools import __try_to_set_owner
from .tools import measure_time, abort
from .tools import _update_setting
from .tools import _get_setting
from .tools import get_git_hash
from .tools import start_postgres_if_local
from .module_tools import _determine_affected_modules_for_ir_field_and_related
from pathlib import Path
from functools import partial


@cli.group(cls=AliasedGroup)
@pass_config
def robot(config):
    pass


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


@robot.command()
@pass_config
@click.pass_context
def setup(ctx, config):
    from .module_tools import Module
    from .odoo_config import MANIFEST, customs_dir
    import yaml

    content = yaml.safe_load(open(customs_dir() / "gimera.yml", "r"))
    for branch in content["repos"]:
        if "marcwimmer/odoo-robot_util" in branch["url"]:
            break
    else:
        content["repos"].append(
            {
                "branch": "${VERSION}",
                "path": "addons_robot",
                "type": "integrated",
                "url": "git@github.com:marcwimmer/odoo-robot_utils",
            }
        )
        yaml.dump(content, open(customs_dir() / "gimera.yml", "w"))

    manifest = MANIFEST()
    if "robot_utils" not in manifest["install"]:
        manifest["install"].append("robot_utils")

    if "addons_robot" not in manifest["addons_paths"]:
        paths = manifest["addons_paths"]
        paths.append("addons_robot")
        manifest["addons_paths"] = paths

    from gimera.gimera import apply as gimera

    ctx.invoke(gimera, recursive=True, update=True, missing=True)
    click.secho(
        "Create now your first robo test with 'odoo robot new smoketest", fg="green"
    )


@robot.command(name="new")
@click.argument("name", required=True)
@pass_config
@click.pass_context
def do_new(ctx, config, name):
    from .odoo_config import MANIFEST, customs_dir

    testdir = customs_dir() / "tests"
    testdir.mkdir(exist_ok=True)

    content = """*** Settings ***
Documentation    Tests button click at instance which starts pipelines. 
Resource         ../addons_robot/robot_utils/keywords/odoo_ee.robot
Test Setup       Setup Test

*** Test Cases ***
Test Synchronous Pipeline No Errors
	Log To Console  Testing it


    """
    testfile = testdir / f"{name}.robot"
    testfile.write_text(content)
    click.secho("Created file: ", fg="green")
    click.secho(testfile)


@robot.command()
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
@click.option(
    "--timeout",
    required=False,
    default=20,
    help="Default timeout for wait until element is visible.",
)
@click.option(
    "-r",
    "--repeat",
    default=1,
    type=int,
)
@click.option(
    "--min-success-required",
    default=100,
    type=int,
    help="Minimum percent success quote - provide with repeat parameter.",
)
@pass_config
@click.pass_context
def run(
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
    timeout,
    repeat,
    min_success_required,
    no_sysexit=False,
):
    PARAM = param
    del param
    started = arrow.utcnow()

    from pathlib import Path
    from .odoo_config import customs_dir
    from .module_tools import DBModules
    from .odoo_config import MANIFEST

    manifest = MANIFEST()

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
    modules = [("install", "robot_utils")]
    if current_version() < 15.0:
        modules.append(("install", "web_selenium"))

    install_odoo_modules, uninstall_odoo_modules = set(), set()
    for mode, mod in odoo_modules:
        if mode == "install":
            install_odoo_modules.add(mod)
        elif mode == "uninstall":
            uninstall_odoo_modules.add(mod)
        else:
            raise NotImplementedError(mode)
    del odoo_modules

    count_faileds = 0
    for i in range(int(repeat)):
        if not config.force and repeat > 1:
            abort(
                "CAUTION: Repeat is set, but not force mode, so database is not recreated."
            )

        if config.force:
            _prepare_fresh_robotest(ctx)

        if install_odoo_modules:

            def not_installed(module):
                data = DBModules.get_meta_data(module)
                if not data:
                    abort(f"Could not get state for {module}")
                return data["state"] != "installed"

            install_modules_to_install = list(
                filter(not_installed, install_odoo_modules)
            )
            if install_modules_to_install:
                click.secho(
                    (
                        "Installing required modules for robot tests: "
                        f"{','.join(install_modules_to_install)}"
                    ),
                    fg="yellow",
                )
                Commands.invoke(
                    ctx,
                    "update",
                    module=install_modules_to_install,
                    no_dangling_check=True,
                )
                click.secho(f"Installed modules {','.join(install_modules_to_install)}")
        if uninstall_odoo_modules:

            def installed(module):
                data = DBModules.get_meta_data(module)
                if not data:
                    abort(f"Could not get state for {module}")
                return data["state"] == "installed"

            modules_to_uninstall = list(filter(installed, uninstall_odoo_modules))
            if modules_to_uninstall:
                click.secho(
                    (
                        "Uninstalling required modules for robot tests: "
                        f"{','.join(modules_to_uninstall)}"
                    ),
                    fg="yellow",
                )
                Commands.invoke(
                    ctx,
                    "uninstall",
                    modules=modules_to_uninstall,
                )

        res = _run_test(
            ctx,
            config,
            user,
            test_name,
            parallel,
            timeout,
            tags,
            PARAM,
            filenames,
            results_file,
            started,
            output_json,
            keep_token_dir,
        )
        if not res:
            count_faileds += 1
        click.secho(
            f"Intermediate stat: {count_faileds} failed - {i+1 - count_faileds} succeeded - to go: {repeat -i - 1}",
            fg="yellow",
        )
    click.secho(
        f"Final stat: {count_faileds} failed of {repeat}",
        fg="green" if not count_faileds else "red",
    )
    success_quote = (repeat - count_faileds) / repeat * 100
    if success_quote < min_success_required:
        if not no_sysexit:
            sys.exit(-1)
        else:
            return False
    return True


def _run_test(
    ctx,
    config,
    user,
    test_name,
    parallel,
    timeout,
    tags,
    PARAM,
    filenames,
    results_file,
    started,
    output_json,
    keep_token_dir,
):
    from .odoo_config import MANIFEST

    manifest = MANIFEST()

    pwd = "robot"
    click.secho(
        f"Password for all users will be set to {pwd}, so that login can happen.",
        fg="yellow",
    )
    Commands.invoke(ctx, "set-password-all-users", password=pwd)
    click.secho("Passwords set")

    def params():
        ODOO_VERSION = str(manifest["version"])
        params = {
            "url": "http://proxy",
            "user": user,
            "dbname": config.DBNAME,
            "password": pwd,
            "selenium_timeout": timeout,  # selenium timeout,
            "parallel": parallel,
            "odoo_version": str(ODOO_VERSION),
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

    from .odoo_config import customs_dir

    workingdir = customs_dir() / (Path(os.getcwd()).relative_to(customs_dir()))
    click.secho(f"Changing working dir: {workingdir}")
    os.chdir(workingdir)

    click.secho(f"Starting test: {params}")
    __dcrun(config, params, pass_stdin=data.decode("utf-8"), interactive=True)

    output_path = config.HOST_RUN_DIR / "odoo_outdir" / "robot_output"
    from .robo_helpers import _eval_robot_output

    res = _eval_robot_output(
        config,
        output_path,
        started,
        output_json,
        token,
        rm_tokendir=not keep_token_dir,
        results_file=results_file,
    )
    return res


def _prepare_fresh_robotest(ctx):
    click.secho("Preparing fresh robo test.", fg="yellow")
    Commands.invoke(ctx, "kill", machines=["postgres"])
    Commands.invoke(ctx, "reset-db")
    Commands.invoke(ctx, "wait_for_container_postgres", missing_ok=True)
    Commands.invoke(ctx, "update", "", tests=False, no_dangling_check=True)
    click.secho("Preparation of tests are done.", fg="yellow")


@robot.command(help="Runs all robots defined in section 'robotests' (filepatterns)")
@click.option(
    "--timeout",
    required=False,
    default=20,
    help="Default timeout for wait until element is visible.",
)
@click.option(
    "--retry",
    required=False,
    default=3,
    help="If test fails - retry.",
)
@pass_config
@click.pass_context
def run_all(
    ctx,
    config,
    timeout,
    retry,
):
    from .odoo_config import MANIFEST, customs_dir
    from .robo_helpers import _get_all_robottest_files
    from .odoo_config import customs_dir

    if not config.DEVMODE:
        abort("Devmode required to run robotests")
    customsdir = customs_dir()

    files = _get_all_robottest_files()
    files = [customsdir / file for file in files]

    for file in files:
        click.secho(f"Running robotest {file}")

        for i in range(retry):
            click.secho(f"Try #{i + 1} of {retry}")
            try:
                res = ctx.invoke(
                    run,
                    file=str(file.relative_to(customsdir)),
                    timeout=timeout,
                    no_sysexit=True,
                )
                if res:
                    break
            except Exception as ex:
                retry += 1
                click.secho(
                    f"Retry at _prepare_fresh_robotest because of {ex}", fg="yellow"
                )
                time.sleep(random.randint(20, 60))
