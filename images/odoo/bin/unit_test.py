#!/usr/bin/env python3
import os
import sys
import click
import subprocess
from odoo_tools.module_tools import Module
from odoo_tools.odoo_config import customs_dir
from odoo_tools.odoo_config import current_version
from pathlib import Path
from tools import exec_odoo
from tools import prepare_run

os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'

if len(sys.argv) == 1:
    print("Missing test file!")
    sys.exit(-1)

loglevel = [x for x in sys.argv[1:] if x.startswith("--log-level=")]
if loglevel:
    loglevel = loglevel[0][len("--log-level="):]
else:
    loglevel = 'debug'

not_interactive = bool([x for x in sys.argv[1:] if x.startswith("--not-interactive")])
if not not_interactive:
    os.environ["PYTHONBREAKPOINT"] = "pudb.set_trace"
else:
    os.environ["PYTHONBREAKPOINT"] = ""

prepare_run()

filepath = Path(sys.argv[1])
if not str(filepath).startswith("/"):
    filepath = Path(os.environ['CUSTOMS_DIR']) / filepath
if not filepath.exists():
    click.secho(f"File not found: {filepath}", fg='red')
    sys.exit(-1)
module = Module(filepath)

# make path relative to links, so that test is recognized by odoo
path = filepath.resolve().absolute()
cmd = [
    '--stop-after-init',
    f'--log-level={loglevel}',
    f'--test-file={path}',
]
if current_version() <= 11.0:
    cmd += [
        '--test-report-directory=/tmp',
    ]
rc = exec_odoo(
    "config_unittest",
    *cmd
)

sys.exit(rc)
