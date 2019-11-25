#!/usr/bin/python3
import traceback
import time
import os
import threading
import subprocess
import click
from pathlib import Path
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
last_mod = ''
last_unit_test = ''
customs_dir = Path(os.environ['CUSTOMS_DIR'])

os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'


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

def endless_loop():
    t = threading.Thread(target=watch_file_and_kill)
    t.daemon = True
    t.start()

    first_run = True

    while True or first_run:
        try:
            if not first_run and not DEBUGGER_WATCH.exists():
                time.sleep(0.2)
                continue
            os.chdir(os.environ["ODOOLIB"])
            if not first_run:
                content = DEBUGGER_WATCH.read_text()
                action = content.split(":")
            if DEBUGGER_WATCH.exists():
                DEBUGGER_WATCH.unlink()
            if first_run or action[0] in ['debug', 'quick_restart']:
                first_run = False
                subprocess.call(['/usr/bin/reset'])
                print("PROXY Port: {}".format(os.environ['PROXY_PORT']))
                subprocess.call(["run_debug.py"])
                continue
            elif action[0] == 'update_view_in_db':
                continue

            elif action[0] in ["update_module", "update_module_full"]:
                kill_odoo()
                module = action[1]
                PARAMS_CONST = ""
                if config['DEVMODE'] == "1" and config.get("NO_QWEB_DELETE", "") != "1":
                    PARAMS_CONST = "--delete-qweb"
                subprocess.call([
                    "update_modules.py",
                    module,
                    "-fast" if action[0] == "update_module" else "",
                    PARAMS_CONST,
                ])
                subprocess.call(["run_debug.py"])

            elif action[0] in ['unit_test', 'last_unit_test']:
                kill_odoo()
                subprocess.call(['/usr/bin/reset'])
                if action[0] == 'unit_test':
                    last_unit_test = str(customs_dir / action[1])
                subprocess.call([
                    "unit_test.py",
                    last_unit_test
                ])

            elif action[0] == 'export_i18n':
                kill_odoo()
                subprocess.call(['/usr/bin/reset'])
                lang = action[1]
                module = action[2]
                subprocess.call([
                    "export_i18n.py",
                    lang,
                    module
                ])
                action = ('debug',)
                continue

            elif action[0] == 'import_i18n':
                kill_odoo()
                subprocess.call(['/usr/bin/reset'])
                lang = action[1]
                filepath = action[2]
                subprocess.call([
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
    endless_loop()


if __name__ == '__main__':
    command_debug()
