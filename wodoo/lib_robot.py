import random
from multiprocessing.dummy import Process
import time
import sys
import uuid
import arrow
import json
import base64
from datetime import datetime
import os
import click

from .odoo_config import current_version
from .tools import __dcrun
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __empty_dir
from .tools import abort
from pathlib import Path

ROBOT_UTILS_GIT = "marcwimmer/odoo-robot_utils"

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
        if ROBOT_UTILS_GIT in branch["url"]:
            break
    else:
        content["repos"].append(
            {
                "branch": "main",
                "path": "addons_robot",
                "type": "integrated",
                "url": f"git@github.com:{ROBOT_UTILS_GIT}",
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
    if os.getenv("SILENT_ROBOT_SETUP") != "1":
        click.secho(
            "Create now your first robo test with 'odoo robot new smoketest", fg="green"
        )


@robot.command(name="new")
@click.argument("name", required=True)
@pass_config
@click.pass_context
def do_new(ctx, config, name):
    from .odoo_config import customs_dir

    os.environ['SILENT_ROBOT_SETUP'] = '1'
    ctx.invoke(setup)

    testdir = customs_dir() / "tests"
    testdir.mkdir(exist_ok=True)

    content = f"""# odoo-require: robot_utils,purchase
# odoo-uninstall: partner_autocomplete

*** Settings ***
Documentation    {name}
Resource         ../addons_robot/robot_utils/keywords/odoo.robot
Resource         ../addons_robot/robot_utils/keywords/tools.robot
Resource         ../addons_robot/robot_utils/keywords/wodoo.robot
Test Setup       Setup Smoketest


*** Test Cases ***
Buy Something and change amount
    # Search for the admin
    # Odoo Load Data    ../data/products.xml 
    MainMenu          purchase.menu_purchase_root
    Odoo Button       Create
    WriteInField      partner_id                     A-Vendor DE
    Odoo Button       text=Add a product
    WriteInField      product_id                     Storage Box    parent=order_line
    WriteInField      product_qty                    50             parent=order_line
    FormSave
    Screenshot
    Odoo Button       name=button_confirm

*** Keywords ***
Setup Smoketest
    Login

"""
    testfile = testdir / f"{name}.robot"
    if testfile.exists():
        abort(f"{testfile} already exists.")
    testfile.write_text(content)
    reltestfile = testfile.relative_to(customs_dir())
    click.secho(f"\n\nRun the test with: robot run {reltestfile}", fg='green')


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
    "-R",
    "--repeat-no-init",
    is_flag=True,
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
    repeat_no_init,
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
            if not repeat_no_init:
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

    pwd = "admin"
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
    click.secho(f"Len of data is: {len(data)}")
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


@robot.command()
@pass_config
@click.pass_context
def cleanup(ctx, config):
    output_path = config.HOST_RUN_DIR / "odoo_outdir" / "robot_output"
    if not output_path.exists():
        return
    __empty_dir(output_path, user_out=False)
    click.secho(f"Cleaned {output_path}")
