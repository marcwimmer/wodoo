#!/usr/bin/env python3
import traceback
import time
import os
import sys
import threading
import subprocess
import click
from pathlib import Path
import tools
from tools import prepare_run
from tools import get_config_file
from odoo_tools.odoo_config import current_version
from odoo_tools.odoo_config import get_env
from odoo_tools.module_tools import update_view_in_db
from odoo_tools.module_tools import Modules
from tools import kill_odoo

config = get_env()
prepare_run()
DEBUGGER_WATCH = Path(os.environ["DEBUGGER_WATCH"])
print("Watching file {}".format(DEBUGGER_WATCH))
last_mod = ''
last_unit_test = ''
customs_dir = Path(os.environ['CUSTOMS_DIR'])

os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'
os.environ["PYTHONBREAKPOINT"] = "pudb.set_trace"

profiling = False
if any(x in ['--profile', '-profile', 'profile'] for x in sys.argv):
    profiling = True


def watch_file_and_kill():
    while True:
        try:
            if DEBUGGER_WATCH.exists():
                content = DEBUGGER_WATCH.read_text()
                action = content.split(":")
                if action[0] and action[0] == 'update_view_in_db':
                    filepath = Path(action[1])
                    lineno = int(action[2])
                    DEBUGGER_WATCH.unlink()
                    update_view_in_db(filepath, lineno)
                else:
                    kill_odoo()
        except Exception:
            msg = traceback.format_exc()
            print(msg)

        time.sleep(0.2)

        # force odoo profiler to output profiling info
        if profiling:
            pidfile = Path(tools.pidfile)
            if pidfile.exists():
                pid = pidfile.read_text().strip()
                os.system(f"kill -3 {pid}")


class Debugger(object):
    def __init__(self, sync_common_modules):
        self.odoolib_path = Path(os.environ['ODOOLIB'])
        self.sync_common_modules = sync_common_modules
        self.first_run = True
        self.last_unit_test = None

    def execpy(self, cmd):
        os.chdir(self.odoolib_path)
        if not cmd[0].startswith("/"):
            cmd = ['python3'] + cmd
        subprocess.call(cmd, cwd=self.odoolib_path)

    def action_debug(self):
        self.first_run = False
        self.execpy(['/usr/bin/reset'])
        if os.getenv("PROXY_PORT", ""):
            print("PROXY Port: {}".format(os.environ['PROXY_PORT']))

        if self.sync_common_modules:
            self.execpy(["/odoolib/put_server_modules_into_odoo_src_dir.py"])
        self.execpy(["run_debug.py"])

    def action_update_module(self, cmd, module):
        kill_odoo()
        PARAMS_CONST = []
        if config['DEVMODE'] == "1" and config.get("NO_QWEB_DELETE", "") != "1":
            PARAMS_CONST += ["--delete-qweb"]
        if cmd == 'update_module':
            PARAMS_CONST += ['--no-tests']
        self.execpy([
            "update_modules.py",
            module,
        ] + PARAMS_CONST)
        self.trigger_restart()

    def action_last_unittest(self):
        if not self.last_unit_test:
            self.trigger_restart()
        self.execpy([
            "unit_test.py",
            self.last_unit_test
        ])

    def action_unittest(self, filepath):
        kill_odoo()
        subprocess.call(['/usr/bin/reset'])
        self.last_unit_test = str(customs_dir / filepath)
        print(f"Running unit test: {last_unit_test}")
        self.execpy([
            "unit_test.py",
            self.last_unit_test
        ])

    def action_export_lang(self, lang, module):
        kill_odoo()
        subprocess.call(['/usr/bin/reset'])
        self.execpy([
            "export_i18n.py",
            lang,
            module
        ])
        self.trigger_restart()

    def action_import_lang(self, lang, filepath):
        kill_odoo()
        self.execpy(['/usr/bin/reset'])
        self.execpy([
            "import_i18n.py",
            lang,
            filepath
        ])
        self.trigger_restart()

    def trigger_restart(self):
        DEBUGGER_WATCH.write_text("debug")

    def endless_loop(self):
        t = threading.Thread(target=watch_file_and_kill)
        t.daemon = True
        t.start()

        action = None

        while True:
            try:
                if not self.first_run and not DEBUGGER_WATCH.exists():
                    time.sleep(0.2)
                    continue
                if not self.first_run:
                    content = DEBUGGER_WATCH.read_text()
                    action = content.split(":")
                if DEBUGGER_WATCH.exists():
                    DEBUGGER_WATCH.unlink()

                if self.first_run or action[0] in ['debug', 'quick_restart']:
                    self.action_debug()
                    continue
                elif action[0] == 'update_view_in_db':
                    continue

                elif action[0] in ["update_module", "update_module_full"]:
                    import pudb
                    pudb.set_trace()
                    self.action_update_module(
                        cmd=action[0],
                        module=action[1]
                    )

                elif action[0] in ['last_unit_test']:
                    self.action_last_unittest()

                elif action[0] in ['unit_test']:
                    self.action_unittest(
                        filepath=action[1],
                    )
                elif action[0] == 'export_i18n':
                    self.action_export_lang(
                        lang=action[1],
                        module=action[2]
                    )
                elif action[0] == 'import_i18n':
                    self.action_import_lang(
                        lang=action[1],
                        filepath=action[2],
                    )

                self.first_run = False
            except Exception:
                msg = traceback.format_exc()
                print(msg)
                time.sleep(1)


@click.command(name='debug')
@click.option("--sync-common-modules", is_flag=True, help="If set, then common modules from framework are copied to addons_tools")
def command_debug(sync_common_modules):
    Debugger(
        sync_common_modules=sync_common_modules,
    ).endless_loop()


if __name__ == '__main__':
    command_debug()
