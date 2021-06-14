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
from tools import get_config_file  # NOQA
from odoo_tools.odoo_config import current_version  # NOQA
from odoo_tools.odoo_config import get_env  # NOQA
from odoo_tools.module_tools import update_view_in_db  # NOQA
from odoo_tools.module_tools import Modules  # NOQA
from tools import kill_odoo

config = get_env()
prepare_run()
DEBUGGER_WATCH = Path(os.environ["DEBUGGER_WATCH"])
print("Watching file {}".format(DEBUGGER_WATCH))
last_mod = ''
last_unit_test = ''
customs_dir = Path(os.environ['CUSTOMS_DIR'])

profiling = False
if any(x in ['--profile', '-profile', 'profile'] for x in sys.argv):
    profiling = True


def watch_file_and_kill():
    while True:
        time.sleep(0.2)

        # force odoo profiler to output profiling info
        if profiling:
            pidfile = Path(tools.pidfile)
            if pidfile.exists():
                pid = pidfile.read_text().strip()
                os.system(f"kill -3 {pid}")


class Debugger(object):
    def __init__(self, sync_common_modules, wait_for_remote, remote_debugging):
        self.odoolib_path = Path(os.environ['ODOOLIB'])
        self.sync_common_modules = sync_common_modules
        self.first_run = True
        self.last_unit_test = None
        self.wait_for_remote = wait_for_remote
        if wait_for_remote:
            remote_debugging = True
        self.remote_debugging = remote_debugging

    def execpy(self, cmd):
        os.chdir(self.odoolib_path)
        if not cmd[0].startswith("/"):
            cmd = ['python3'] + cmd
        return not subprocess.call(cmd, cwd=self.odoolib_path) # exitcode

    def action_debug(self):
        self.first_run = False
        self.execpy(['/usr/bin/reset'])
        if os.getenv("PROXY_PORT", ""):
            print("PROXY Port: {}".format(os.environ['PROXY_PORT']))
        if os.getenv("ODOO_PYTHON_DEBUG_PORT", ""):
            print("PTHON REMOTE DEBUGGER PORT: {}".format(os.environ['ODOO_PYTHON_DEBUG_PORT']))
        print(f"Using tracing: {os.getenv('PYTHONBREAKPOINT')}")
        print(f"remote debugg: {self.remote_debugging}, waiting for debugger: {self.wait_for_remote}")

        if self.sync_common_modules:
            self.execpy(["/odoolib/put_server_modules_into_odoo_src_dir.py"])
        cmd = ["run_debug.py"]
        if self.remote_debugging:
            cmd += ["--remote-debug"]
        if self.wait_for_remote:
            cmd += ["--wait-for-remote"]
        print(f"executing: {cmd}")
        self.execpy(cmd)

    def action_update_module(self, cmd, module):
        kill_odoo()
        PARAMS_CONST = []
        if config['DEVMODE'] == "1" and config.get("NO_QWEB_DELETE", "") != "1":
            PARAMS_CONST += ["--delete-qweb"]
        if cmd == 'update_module':
            PARAMS_CONST += ['--no-tests']
        if self.execpy([
                "update_modules.py",
                module,
        ] + PARAMS_CONST):
            self.trigger_restart()

    def action_last_unittest(self):
        if not self.last_unit_test:
            self.trigger_restart()
        self.action_unittest(self.last_unit_test)

    def action_unittest(self, filepath):
        kill_odoo()
        subprocess.call(['/usr/bin/reset'])
        self.last_unit_test = str(customs_dir / filepath)
        print(f"Running unit test: {last_unit_test}")
        args = []
        if self.wait_for_remote:
            args += [
                "--wait-for-remote"
            ]
            print(f"Please connect your external debugger to: {os.environ['ODOO_PYTHON_DEBUG_PORT']}")
        self.execpy([
            "unit_test.py",
            self.last_unit_test,
        ] + args)

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
                    DEBUGGER_WATCH.unlink()
                    action = content.split(":")

                if self.first_run or action[0] in ['debug', 'quick_restart']:
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_debug)
                    thread1.daemon = True
                    thread1.start()

                if action[0] in ['restart']:
                    kill_odoo()
                    self.trigger_restart()

                elif action[0] == 'update_view_in_db':
                    filepath = Path(action[1])
                    lineno = int(action[2])
                    update_view_in_db(filepath, lineno)

                elif action[0] in ["update_module", "update_module_full"]:
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_update_module, kwargs=dict(
                        cmd=action[0],
                        module=action[1]
                    ))
                    thread1.daemon = True
                    thread1.start()

                elif action[0] in ['last_unit_test']:
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_last_unittest)
                    thread1.daemon = True
                    thread1.start()

                elif action[0] in ['unit_test']:
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_unittest, kwargs=dict(
                        filepath=action[1],
                    ))
                    thread1.daemon = True
                    thread1.start()

                elif action[0] == 'export_i18n':
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_export_lang, kwargs=dict(
                        lang=action[1],
                        module=action[2]
                    ))
                    thread1.daemon = True
                    thread1.start()

                elif action[0] == 'import_i18n':
                    kill_odoo()
                    thread1 = threading.Thread(target=self.action_import_lang, kwargs=dict(
                        lang=action[1],
                        filepath=action[2],
                    ))
                    thread1.daemon = True
                    thread1.start()

                self.first_run = False

            except Exception:
                msg = traceback.format_exc()
                print(msg)
                time.sleep(1)


@click.command(name='debug')
@click.option("-s", "--sync-common-modules", is_flag=True, help="If set, then common modules from framework are copied to addons_tools")
@click.option('-q', '--debug-queuejobs', is_flag=True)
@click.option('-w', '--wait-for-remote', is_flag=True)
@click.option('-r', '--remote-debugging', is_flag=True)
def command_debug(sync_common_modules, debug_queuejobs, wait_for_remote, remote_debugging):
    if debug_queuejobs:
        os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'
    if remote_debugging:
        os.environ["PYTHONBREAKPOINT"] = "debugpy.set_trace"
    else:
        os.environ["PYTHONBREAKPOINT"] = "pudb.set_trace"

    Debugger(
        sync_common_modules=sync_common_modules,
        wait_for_remote=wait_for_remote,
        remote_debugging=remote_debugging,
    ).endless_loop()


if __name__ == '__main__':
    command_debug()
