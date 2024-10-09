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
from ..lib_composer import config as config_command
from ..lib_control import build, up, down
from ..click_config import Config
from ..lib_module import update, uninstall
from ..lib_backup import backup_db, restore_db
from contextlib import contextmanager


# class BaseTestClass:
#     def config_path(self, projectname):
#         return Path(os.path.expanduser(f"~/.odoo/settings.{projectname}"))

#     @property
#     def script_dir(self):
#         return Path(
#             os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
#         )

#     def _write_configuration(self, configuration):
#         configuration.setdefault("PROXY_PORT", "1200")
#         configuration.setdefault("RUN_CRONJOBS", "0")
#         txt = []
#         for k, v in configuration.items():
#             txt.append(f"{k}={v}")
#         self.config_path(self.project_name).write_text("\n".join(txt))

#     @property
#     def python(self):
#         return sys.executable

#     @pytest.fixture(scope="function", autouse=True)
#     def _setup_clirunner(self):
#         self.runner = CliRunner()

#     @pytest.fixture(scope="function", autouse=True)
#     def _setup_odoo(self):

#         self.project_name = "wodootest"
#         os.chdir(self.path)
#         shutil.copy(self.script_dir / "gimera.yml", self.path)
#         shutil.copy(self.script_dir / "MANIFEST", self.path)
#         subprocess.check_call(["git", "init", "."], cwd=self.path)
#         subprocess.check_call(
#             ["git", "config", "init.defaultBranch", "main"], cwd=self.path
#         )
#         subprocess.check_call(["git", "add", "."], cwd=self.path)
#         subprocess.check_call(
#             ["git", "commit", "-m", "empty", "--allow-empty"], cwd=self.path
#         )
#         subprocess.check_call(["gimera", "apply"], cwd=self.path)

#         self.config = Config(force=True, project_name=self.project_name)
#         self._write_configuration({})
#         # make a convenient file for easy testing
#         Path("odoo.sh").write_text(
#             "#!/bin/bash\n" f'odoo -p {self.project_name} "$@"\n'
#         )
#         os.system("chmod a+x odoo.sh")
#         self._adapt_requirement_for_m1()
#         self.run(do_reload, ["--demo"])
#         try:
#             yield
#         except Exception:
#             try:
#                 self.run(down, ["-v"])
#             except Exception:
#                 pass
#             raise

#     def _install_module(self, path):
#         shutil.copytree(path, self.path / "odoo" / "addons" / path.name)
#         self.run(update, [path.name, "-O"])

#     def _retrybuild(self):
#         # zfs has some problems; needs several builds for multi stage builds
#         MAX = 5
#         for i in range(MAX):
#             try:
#                 self.run(build, catch_exceptions=False)
#             except:
#                 if i == MAX - 1:
#                     raise
#             else:
#                 break

#     def _replace_in_file(self, path, search, replace):
#         content = path.read_text()
#         content = content.replace(search, replace)
#         path.write_text(content)

#     def _adapt_requirement_for_m1(self):
#         file = self.path / "odoo" / "requirements.txt"
#         reqs = file.read_text().splitlines()
#         version = float(eval((self.path / "MANIFEST").read_text())["version"])
#         if version <= 15:
#             reqs = [x for x in reqs if "greenlet" not in x]
#             reqs = [x for x in reqs if "gevent" not in x]
#             reqs.append("greenlet")
#             reqs.append("gevent==21.12.0")

#         file.write_text("\n".join(reqs))

#     def run(self, cmd, params=None, catch_exceptions=True):
#         params = params or []
#         res = self.runner.invoke(
#             cmd, params, obj=self.config, catch_exceptions=catch_exceptions
#         )
#         if catch_exceptions:
#             if res.exit_code:
#                 traceback.print_exception(*res.exc_info)
#                 raise Exception("Execution failed")
#         return res
