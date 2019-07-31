#!/usr/bin/env python3
import time
import os
import threading
import subprocess
import click
from pathlib import Path
from tools import prepare_run
from tools import get_config_file
from module_tools.odoo_config import current_version
from module_tools.odoo_config import get_env
from module_tools.module_tools import update_view_in_db
from module_tools.module_tools import Modules
from tools import kill_odoo

config = get_env()
prepare_run()
DEBUGGER_WATCH = Path(os.environ["DEBUGGER_WATCH"])
last_mod = ''
last_unit_test = ''

# append configuration option to run old odoo on port 8072
if current_version() <= 7.0:
    conf = Path(get_config_file('config_debug'))
    with conf.open('a') as f:
        f.write('\n')
        f.write("xmlrpc_port=8072")
        f.write('\n')
    del conf


def watch_file_and_kill():
    last_mod = DEBUGGER_WATCH.stat().st_mtime
    while True:
        try:
            new_mod = DEBUGGER_WATCH.stat().st_mtime
        except Exception:
            pass
        else:
            if new_mod != last_mod:
                try:
                    content = DEBUGGER_WATCH.read_text()
                    action = content.split(":")
                    if action[0]:
                        if action[0] == 'update_view_in_db':
                            filepath = Path(action[1])
                            lineno = int(action[2])
                            update_view_in_db(filepath, lineno)
                        else:
                            kill_odoo()
                except Exception as e:
                    print(e)
            last_mod = new_mod

        time.sleep(0.2)

def endless_loop():
    global last_mod
    t = threading.Thread(target=watch_file_and_kill)
    t.daemon = True
    t.start()
    DEBUGGER_WATCH.write_text("debug")
    while True:
        new_mod = DEBUGGER_WATCH.stat().st_mtime
        if new_mod != last_mod:
            os.chdir(os.environ["ODOOLIB"])
            content = DEBUGGER_WATCH.read_text()
            action = content.split(":")
            if action[0] in ['debug', 'quick_restart']:
                subprocess.call(['/usr/bin/reset'])
                subprocess.call(["run_debug.py"])

            elif action[0] in ["update_module", "update_module_full"]:
                module = action[1]
                PARAMS_CONST = ""
                if config['DEVMODE'] == "1":
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
                    last_unit_test = action[1]
                subprocess.call([
                    "unit_test.py",
                    last_unit_test
                ])

            elif action[0] == 'export_i18n':
                subprocess.call(['/usr/bin/reset'])
                lang = action[1]
                module = action[2]
                subprocess.call([
                    "export_i18n.py",
                    lang,
                    module
                ])

            elif action[0] == 'import_i18n':
                subprocess.call(['/usr/bin/reset'])
                lang = action[1]
                filepath = action[2]
                subprocess.call([
                    "import_i18n.py",
                    lang,
                    filepath
                ])
            last_mod = new_mod
        time.sleep(0.2)

@click.command(name='debug')
def command_debug():
    endless_loop()


if __name__ == '__main__':
    command_debug()
