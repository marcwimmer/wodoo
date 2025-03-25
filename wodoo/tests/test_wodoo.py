import pytest
import shutil
from pathlib import Path
from ..lib_control import up
from ..lib_db import reset_db
from ..lib_module import update, UpdateException
from .basetest_class import BaseTestClass


class TestWodoo(BaseTestClass):
    def setup_method(self, method):
        self.path = Path("/tmp/wodootest/" + method.__name__)
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(exist_ok=True, parents=True)

    def teardown_method(self, method):
        if self.path.exists():
            try:
                shutil.rmtree(self.path)
            except Exception:
                pass

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
        Path(
            "odoo/addons/module_respartner_dummyfield1/__init__.py"
        ).write_text("")
        view_file = Path(
            "odoo/addons/module_respartner_dummyfield1/partnerview.xml"
        )
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
