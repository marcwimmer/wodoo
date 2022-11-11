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
from ..lib_composer import do_reload, config
from ..lib_control import build, up, down
from ..click_config import Config
from ..lib_db import reset_db
from ..lib_module import update, uninstall

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


def _adapt_requirement_for_m1(path):
    file = path / "odoo" / "requirements.txt"
    reqs = file.read_text().splitlines()
    version = float(eval((path / "MANIFEST").read_text())["version"])
    if version <= 15:
        reqs = [x for x in reqs if "greenlet" not in x]
        reqs = [x for x in reqs if "gevent" not in x]
        reqs.append("greenlet")
        reqs.append("gevent==21.12.0")

    file.write_text("\n".join(reqs))


def _prepare_path(project_name, temppath, configuration):
    if "PROXY_PORT" not in configuration:
        configuration += "\nPROXY_PORT=1200"
    path = temppath / "smoke"
    path.mkdir()
    os.chdir(path)
    _setup_odoo(path)
    config_path(project_name).write_text(configuration)
    config = Config(force=True, project_name=project_name)
    # make a convenient file for easy testing
    Path("odoo.sh").write_text(
        "#!/bin/bash\n"
        f"odoo -p {project_name} \"$@\"\n"
    )
    os.system("chmod a+x odoo.sh")
    return config, path


def _install_module(config, runner, path):
    shutil.copytree(path, Path(os.getcwd()) / "odoo" / "addons" / path.name)
    _eval_res(
        runner.invoke(update, [path.name, "-O"], obj=config, catch_exceptions=True)
    )


def _remove_dockercontainers(project_name):
    assert len(project_name) > 5
    for containerid in subprocess.check_output(
        ["docker", "ps", "-a", "-q", "--filter", f"name={project_name}"],
        encoding="utf8",
    ).splitlines():
        subprocess.check_call(["docker", "stop", containerid])
        subprocess.check_call(["docker", "rm", "-f", containerid])


# def test_smoke(runner, temppath):
#     from .. import pass_config

#     (
#         config,
#         path,
#     ) = _prepare_path("smoketest", temppath, configuration=("RUN_CRONJOBS=0"))
#     # -------------------------------------------------------
#     _remove_dockercontainers(config.project_name)
#     _eval_res(runner.invoke(do_reload, obj=config, catch_exceptions=True))
#     _retrybuild(config, runner)
#     try:
#         pass
#     except Exception:
#         try:
#             _eval_res(runner.invoke(down, ["-v"], obj=config, catch_exceptions=True))
#         except:
#             pass
#         raise


def _retrybuild(config, runner):
    # zfs has some problems; needs several builds for multi stage builds
    MAX = 5
    for i in range(MAX):
        try:
            _eval_res(runner.invoke(build, obj=config, catch_exceptions=True))
        except:
            if i == MAX - 1:
                raise
        else:
            break


def _replace_in_file(path, search, replace):
    content = path.read_text()
    content = content.replace(search, replace)
    path.write_text(content)


def test_update_with_broken_view(runner, temppath):
    """
    Situation:
    Two modules add fields and adapt same view by inheriting them.
    Then field is removed in one of the modules.
    
    """
    (
        config,
        path,
    ) = _prepare_path("wodooviewconflict", temppath, configuration=("RUN_CRONJOBS=0"))

    _remove_dockercontainers(config.project_name)
    _adapt_requirement_for_m1(path)
    import pudb;pudb.set_trace()
    _eval_res(runner.invoke(do_reload, ["--demo"], obj=config, catch_exceptions=True))
    _retrybuild(config, runner)
    _eval_res(runner.invoke(up, ["-d"], obj=config, catch_exceptions=True))
    output = runner.invoke("config", ["--full"], obj=config, catch_exceptions=True)
    click.secho(output, fg='yellow')
    import pudb;pudb.set_trace()
    try:
        _eval_res(runner.invoke(reset_db, obj=config, catch_exceptions=True))
        _eval_res(runner.invoke(update, obj=config, catch_exceptions=True))
        _install_module(config, runner, current_dir / "module_respartner_dummyfield1")
        _install_module(config, runner, current_dir / "module_respartner_dummyfield2")

        # now drop dumm1 field and update both modules
        Path("odoo/addons/module_respartner_dummyfield1/__init__.py").write_text("")
        view_file = Path(
            "odoo/addons/module_respartner_dummyfield1/partnerview.xml"
        )
        _replace_in_file(view_file, "dummy1", "create_date")
        _eval_res(
            runner.invoke(
                update,
                ["module_respartner_dummyfield1", "module_respartner_dummyfield2"],
                obj=config,
                catch_exceptions=True,
            )
        )
        import pudb;pudb.set_trace()

    except Exception:
        try:
            _eval_res(runner.invoke(down, ["-v"], obj=config, catch_exceptions=True))
        except:
            pass
        raise
