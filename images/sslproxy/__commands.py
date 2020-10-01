#!/bin/env python3
import requests
import click
import yaml
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
from odoo_tools import files

@cli.group(cls=AliasedGroup)
@pass_config
def sslproxy(config):
    pass

@sslproxy.command(help="Removes existing SSL certificates; restart to renew them")
@pass_config
@click.pass_context
def clean(ctx, config):
    path = Path(config.dirs['run']) / 'ssl'
    __empty_dir(path, user_out=True)
