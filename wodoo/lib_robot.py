import subprocess
import random
import time
import sys
import uuid
import arrow
import json
import base64
import os
import click

from .odoo_config import current_version
from .tools import __dcrun
from .tools import __dc  # NOQA
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __empty_dir
from .tools import abort
from .tools import __assure_gitignore
from .tools import _get_available_robottests
from pathlib import Path

ROBOT_UTILS_GIT = "marcwimmer/odoo-robot_utils"


@cli.group(cls=AliasedGroup)
@pass_config
def robot(config):
    pass


@robot.command()
@pass_config
@click.pass_context
def setup(ctx, config):
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

    _setup_robot_env(config, ctx)

    ctx.invoke(gimera, recursive=True, update=True, missing=True)
    if os.getenv("SILENT_ROBOT_SETUP") != "1":
        click.secho(
            "Create now your first robo test with 'odoo robot new smoketest",
            fg="green",
        )


def _setup_robot_env(config, ctx):
    # e.g. for robotcode extension used in vscdoe
    path = Path(os.path.expanduser("~/.robotenv"))
    reqfile = config.dirs["images"] / "robot" / "requirements.txt"

    if path.exists():
        return
    click.secho(
        "Setting up virtual environment for robotframework", fg="yellow"
    )
    subprocess.run(["python3", "-m", "venv", path], check=True)

    click.secho("Installing requirements for robotframework", fg="yellow")
    click.secho(reqfile.read_text(), fg="yellow")
    subprocess.run(
        [str(path / "bin" / "pip"), "install", "-r", reqfile], check=True
    )


@robot.command(name="new")
@click.argument("name", required=True)
@pass_config
@click.pass_context
def do_new(ctx, config, name):
    from .odoo_config import customs_dir

    os.environ["SILENT_ROBOT_SETUP"] = "1"
    ctx.invoke(setup)

    testdir = customs_dir() / "tests"
    testdir.mkdir(exist_ok=True)

    content_file = (
        customs_dir()
        / "addons_robot"
        / "robot_utils"
        / "tests"
        / "test_template.robot"
    )
    if not content_file.exists():
        raise Exception(f"File not found: {content_file}")
    content = content_file.read_text()
    testfile = testdir / f"{name}.robot"
    if testfile.exists():
        abort(f"{testfile} already exists.")
    testfile.write_text(content)
    reltestfile = testfile.relative_to(customs_dir())
    click.secho(f"\n\nRun the test with: robot run {reltestfile}", fg="green")


@robot.command()
@click.argument(
    "file", required=False, shell_complete=_get_available_robottests
)
@click.option("-u", "--user", default="admin")
@click.option("-a", "--all", is_flag=True)
@click.option("-n", "--test_name", is_flag=False)
@click.option(
    "-p",
    "--param",
    multiple=True,
    help="e.g. --param key1=value1 --param key2=value2",
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
    help=(
        "If set, then a json is printed to console, with detailed informations"
    ),
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
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Use Visual Code to debug debugpy - connect the created profile.",
)
@click.option(
    "-M",
    "--no-install-further-modules",
    is_flag=True,
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
    debug=False,
    no_install_further_modules=False,
):
    PARAM = param
    del param
    started = arrow.utcnow()

    from .odoo_config import customs_dir
    from .module_tools import DBModules
    from .odoo_config import MANIFEST

    manifest = MANIFEST()

    if not config.devmode and not config.force:
        click.secho(
            (
                "Devmode required to run unit tests. Database will be destroyed."
            ),
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
    odoo_modules = set(
        get_odoo_modules(config.verbose, filenames, customs_dir())
    )
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

        if config.force and not no_install_further_modules:
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
                click.secho(
                    f"Installed modules {','.join(install_modules_to_install)}"
                )
        if uninstall_odoo_modules:

            def installed(module):
                data = DBModules.get_meta_data(module)
                if not data:
                    abort(f"Could not get state for {module}")
                return data["state"] == "installed"

            modules_to_uninstall = list(
                filter(installed, uninstall_odoo_modules)
            )
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
            debug=debug,
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
    debug=False,
    browser=None,
):
    from .odoo_config import MANIFEST

    headless = os.getenv("IS_COBOT_CONTAINER") != "1"

    manifest = MANIFEST()
    if not browser:
        browser = "chrome"

    # if debug:
    #     _setup_visual_code_robot(ctx, config)

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
            "SELENIUM_TIMEOUT": timeout,  # selenium timeout,
            "parallel": parallel,
            "odoo_version": str(ODOO_VERSION),
            "headless": headless,
            "browser": browser,
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
            "debug": debug,
            "params": params(),
        }
    )
    data = base64.b64encode(data.encode("utf-8")).decode("utf8")

    params = [
        "robot",
    ]

    from .odoo_config import customs_dir

    workingdir = customs_dir() / (Path(os.getcwd()).relative_to(customs_dir()))
    click.secho(f"Changing working dir: {workingdir}")
    os.chdir(workingdir)

    click.secho(f"Starting test: {params}")
    if os.getenv("IS_COBOT_CONTAINER") == "1":
        Path("/tmp/archive").write_text(data)
        subprocess.run(
            ["/usr/bin/python3", "/opt/robot/robotest.py"],
            env=os.environ,
        )
    else:
        __dcrun(config, params, pass_stdin=data, interactive=True)
    del data

    output_path = config.HOST_RUN_DIR / "odoo_outdir" / "robot_output"
    from .robo_helpers import _eval_robot_output

    Commands.invoke(ctx, "restart", machines=["seleniumdriver"])

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


@robot.command(
    help="Runs all robots defined in section 'robotests' (filepatterns)"
)
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
    from .odoo_config import customs_dir
    from .robo_helpers import _get_all_robottest_files
    from .odoo_config import customs_dir

    if not config.DEVMODE:
        abort("Devmode required to run robotests")
    customsdir = customs_dir()

    # if debug:
    #     _setup_visual_code_robot(ctx, config)

    files = _get_all_robottest_files()
    files = [customsdir / file for file in files]

    for file in files:
        click.secho(f"Running robotest {file}")

        for i in range(retry):
            click.secho(
                f"Try #{i + 1} of {retry} for {file.parent}/{file.name}"
            )
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
                    f"Retry at _prepare_fresh_robotest because of {ex}",
                    fg="yellow",
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


def _setup_visual_code_robot(ctx, config):
    from .odoo_config import customs_dir

    path = customs_dir() / ".vscode" / "launch.json"
    if not path.exists():
        config = {
            "version": "0.2.0",
            "configurations": [],
        }
    else:
        config = json.loads(path.read_text())
    name = "Robot Framework Debugger (local attach)"

    # "type": "robotframework-lsp",
    target_conf = {
        "name": name,
        "type": "python",
        "request": "attach",
        "connect": {"host": "localhost", "port": 5678},
        "pathMappings": [
            {
                "localRoot": "${workspaceFolder}",
                "remoteRoot": "/home/parallels/projects/hpn",
            }
        ],
    }
    conf2 = []
    for conf in config.get("configurations", []):
        if name == conf["name"]:
            continue
        conf2.append(conf)
    conf2.insert(0, target_conf)
    config["configurations"] = conf2
    path.write_text(json.dumps(config, indent=4))


@robot.command(help="Access cobot on http://<host>/cobot")
@pass_config
@click.pass_context
def start_cobot(ctx, config):
    __dc(config, ["up", "-d", "novnc_cobot", "cobot", "proxy"])

    click.secho(f"Access cobot at: ")
    click.secho(
        f"\n{config.EXTERNAL_DOMAIN}:{config.PROXY_PORT}/cobot\n\n",
        fg="green",
        bold=True,
    )


@robot.command(help="Creates .robot-vars")
@click.option("-P", "--userpassword", required=False)
@pass_config
@click.pass_context
def make_variable_file(ctx, config, userpassword=None):
    host = os.getenv("ROBO_ODOO_HOST") or config.EXTERNAL_DOMAIN
    url = f"http://{host}:{config.PROXY_PORT}"
    from .odoo_config import customs_dir

    path = customs_dir() / ".robot-vars"
    if not path.exists():
        path.write_text("{}")
    data = json.loads(path.read_text())
    data.setdefault("TOKEN", 100)
    if userpassword:
        data["ROBO_ODOO_PASSWORD"] = userpassword
    data.setdefault("ROBO_ODOO_PASSWORD", "admin")
    data["ROBO_ODOO_PORT"] = int(config.PROXY_PORT)
    data["ROBO_ODOO_USER"] = "admin"
    data["ROBO_ODOO_DB"] = config.DBNAME
    data["ROBO_ODOO_VERSION"] = current_version()
    data["TEST_RUN_INDEX"] = 0
    data["TEST_DIR"] = str(customs_dir() / "robot-output")
    Path(data["TEST_DIR"]).mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=4))

    __assure_gitignore(customs_dir() / ".gitignore", ".robot-vars")


Commands.register(make_variable_file, "robot:make-var-file")
Commands.register(run, "robot:run")
