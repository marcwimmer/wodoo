import os
import traceback
import click
import pytest
import inspect
import sys
import shutil
import tempfile
from pathlib import Path
import subprocess
from click.testing import CliRunner
from ..lib_composer import do_reload
from ..lib_control import build, up
from ..click_config import Config
from ..lib_db import reset_db
from ..lib_module import update

current_dir = Path(
    os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
)


@pytest.fixture(scope="module")
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def python():
    return sys.executable


@pytest.fixture(autouse=True)
def temppath():
    path = Path("/tmp/wodootest")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(exist_ok=True)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def config_path(projectname):
    return Path(os.path.expanduser(f"~/.odoo/settings.{projectname}"))


def _setup_odoo(path):
    shutil.copy(current_dir / "gimera.yml", path)
    shutil.copy(current_dir / "MANIFEST", path)
    subprocess.check_call(["git", "init", "."], cwd=path)
    subprocess.check_call(["gimera", "apply"], cwd=path)


def _eval_res(res):
    if res.exit_code:
        traceback.print_exception(*res.exc_info)
        raise Exception("Execution failed")


def test_smoke(runner, temppath):
    from .. import pass_config

    path = temppath / "smoke"
    path.mkdir()
    os.chdir(path)
    project_name = "wodootestsmoke"

    # -------------------------------------------------------
    _setup_odoo(path)
    config_path(project_name).write_text("RUN_CRONJOBS=0")
    config = Config(force=True, project_name=project_name)
    _eval_res(runner.invoke(do_reload, obj=config, catch_exceptions=True))


def test_update_with_broken_view(runner, temppath):
    path = temppath / "smoke"
    path.mkdir()
    os.chdir(path)
    project_name = "wodootestsmoke"
    _setup_odoo(path)
    config_path(project_name).write_text("RUN_CRONJOBS=0")
    config = Config(force=True, project_name=project_name)
    _eval_res(runner.invoke(do_reload, demo=True, obj=config, catch_exceptions=True))
    _eval_res(runner.invoke(build, demo=True, obj=config, catch_exceptions=True))
    _eval_res(runner.invoke(reset_db, obj=config, catch_exceptions=True))
    _eval_res(runner.invoke(update, obj=config, catch_exceptions=True))
