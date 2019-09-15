#!/bin/env python3
import requests
import click
import inquirer
import os
import subprocess
from pathlib import Path
try:
    injected_globals = injected_globals # NOQA
except Exception:
    pass
from odoo_tools.lib_clickhelpers import AliasedGroup
from odoo_tools.tools import __empty_dir, __dc
from odoo_tools import cli, pass_config

@cli.group(cls=AliasedGroup)
@pass_config
def sslproxy(config):
    pass

def _safe_delete(f):
    if f.exists():
        f.unlink()

@sslproxy.command()
@click.option('--test', is_flag=True, help="Set if you're testing your setup to avoid hitting request limits")
@pass_config
@click.pass_context
def init(ctx, config, test):
    click.secho("Caution: Port 443 and 80 must be temporarily accessible.", fg='yellow', bold=True)
    __dc([
        'up',
        'letsencrypt'
    ])

@sslproxy.command()
@pass_config
@click.pass_context
def clean(ctx, config):
    path = Path(config.HOST_RUN_DIR) / 'ssl'
    __empty_dir(path, user_out=True)
