import os
import time
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
from ..lib_db import reset_db
from ..lib_module import update, uninstall, UpdateException
from ..lib_backup import backup_db, restore_db
from contextlib import contextmanager
from .basetest_class import BaseTestClass


class TestWodoo(BaseTestClass):
    def setup_method(self, method):
        self.path = Path("/tmp/wodootest/" + method.__name__)
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(exist_ok=True, parents=True)

    def teardown_method(self, method):

        if self.path.exists():
            shutil.rmtree(self.path)

    # def test_smoke(self):
    #     pass

    # def test_backup(self):
    #     pass

    def test_update_with_broken_view(self):
        """
        Situation:
        Two modules add fields and adapt same view by inheriting them.
        Then field is removed in one of the modules.

        """
        self.run(up, ["-d"])
        self.run(reset_db)
        self.run(update)
        self._install_module(self.script_dir / "module_respartner_dummyfield1")
        self._install_module(self.script_dir / "module_respartner_dummyfield2")

        # now drop dummy2 field and update both modules
        Path("odoo/addons/module_respartner_dummyfield1/__init__.py").write_text("")
        view_file = Path("odoo/addons/module_respartner_dummyfield1/partnerview.xml")
        self._replace_in_file(view_file, "dummy1", "create_date")
        with pytest.raises(UpdateException):
            self.run(
                update,
                ["module_respartner_dummyfield2"],
                catch_exceptions=False,
            )
        self.run(
            update,
            [
                "module_respartner_dummyfield1",
                "module_respartner_dummyfield2",
                "--recover-view-error",
                "--non-interactive",
            ],
            catch_exceptions=False,
        )
