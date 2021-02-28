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
import argparse
parser = argparse.ArgumentParser(description='Unittest.')
parser.add_argument('--log-level')
parser.add_argument('--not-interactive', action="store_true")
parser.add_argument('test_file')
parser.set_defaults(log_level='debug')
args = parser.parse_args()

os.environ['TEST_QUEUE_JOB_NO_DELAY'] = '1'

if not args.not_interactive:
    os.environ["PYTHONBREAKPOINT"] = "pudb.set_trace"
else:
    os.environ["PYTHONBREAKPOINT"] = "0"

prepare_run()

filepath = Path(args.test_file)
if not str(filepath).startswith("/"):
    filepath = Path(os.environ['CUSTOMS_DIR']) / filepath
if not filepath.exists():
    click.secho(f"File not found: {filepath}", fg='red')
    sys.exit(-1)
module = Module(filepath)

cmd = [
    '--stop-after-init',
    f'--log-level={args.log_level}',
    f'--test-file={filepath.resolve().absolute()}',
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
