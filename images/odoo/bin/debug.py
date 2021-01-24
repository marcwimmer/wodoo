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
    def __init__(self):
        self.odoolib_path = Path(os.environ['ODOOLIB'])
        pass

    def execpy(self, cmd):
        os.chdir(self.odoolib_path)
        if not cmd[0].startswith("/"):
            cmd = ['python3'] + cmd
        subprocess.call(cmd, cwd=self.odoolib_path)

    def endless_loop(self):
        t = threading.Thread(target=watch_file_and_kill)
        t.daemon = True
        t.start()

        first_run = True
        action = None

        while True or first_run:
            try:
                if not first_run and not DEBUGGER_WATCH.exists():
                    time.sleep(0.2)
                    continue
                if not first_run:
                    content = DEBUGGER_WATCH.read_text()
                    action = content.split(":")
                if DEBUGGER_WATCH.exists():
                    DEBUGGER_WATCH.unlink()
                if first_run or action[0] in ['debug', 'quick_restart']:
                    first_run = False
                    self.execpy(['/usr/bin/reset'])
                    if os.getenv("PROXY_PORT", ""):
                        print("PROXY Port: {}".format(os.environ['PROXY_PORT']))

                    self.execpy(["/odoolib/put_server_modules_into_odoo_src_dir.py"])
                    self.execpy(["run_debug.py"])
                    continue
                elif action[0] == 'update_view_in_db':
                    continue

                elif action[0] in ["update_module", "update_module_full"]:
                    kill_odoo()
                    module = action[1]
                    PARAMS_CONST = []
                    if config['DEVMODE'] == "1" and config.get("NO_QWEB_DELETE", "") != "1":
                        PARAMS_CONST += ["--delete-qweb"]
                    if action[0] == 'update_module':
                        PARAMS_CONST += ['--no-tests']
                    self.execpy([
                        "update_modules.py",
                        module,
                    ] + PARAMS_CONST)
                    self.execpy(["run_debug.py"])

                elif action[0] in ['unit_test', 'last_unit_test']:
                    kill_odoo()
                    subprocess.call(['/usr/bin/reset'])
                    if action[0] == 'unit_test':
                        last_unit_test = str(customs_dir / action[1])
                    print("Running unit test: ", last_unit_test)
                    self.execpy([
                        "unit_test.py",
                        last_unit_test
                    ])

                elif action[0] == 'export_i18n':
                    kill_odoo()
                    subprocess.call(['/usr/bin/reset'])
                    lang = action[1]
                    module = action[2]
                    self.execpy([
                        "export_i18n.py",
                        lang,
                        module
                    ])
                    action = ('debug',)
                    continue

                elif action[0] == 'import_i18n':
                    kill_odoo()
                    self.execpy(['/usr/bin/reset'])
                    lang = action[1]
                    filepath = action[2]
                    self.execpy([
                        "import_i18n.py",
                        lang,
                        filepath
                    ])
                    action = ('debug',)
                    continue
            except Exception:
                msg = traceback.format_exc()
                print(msg)
                time.sleep(1)


@click.command(name='debug')
def command_debug():
    Debugger().endless_loop()


if __name__ == '__main__':
    command_debug()
