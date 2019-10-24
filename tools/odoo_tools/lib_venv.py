import yaml
from pathlib import Path
import subprocess
import inquirer
import sys
import threading
import time
import traceback
from datetime import datetime
import shutil
import hashlib
import os
import tempfile
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .tools import __dc
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import _askcontinue
from .tools import __append_line
from .tools import __get_odoo_commit
from .odoo_config import current_customs
from .odoo_config import customs_dir
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def venv(config):
    pass


@venv.command()
@pass_config
def setup(config):
    dir = customs_dir()
    os.chdir(dir)
    venv_dir = dir / '.venv'
    gitignore = dir / '.gitignore'
    if '.venv' not in gitignore.read_text().split("\n"):
        with gitignore.open("a") as f:
            f.write("\n.venv\n")

    subprocess.check_call(["python3", "-m", "venv", venv_dir.absolute()])

    click.secho("Please execute following commands in your shell:", bold=True)
    click.secho("brew install postgresql")
    click.secho("source '{}'".format(venv_dir / 'bin' / 'activate'))
    click.secho("pip3 install -r https://raw.githubusercontent.com/odoo/odoo/{}/requirements.txt".format(current_version()))
    requirements1 = Path(__file__).parent.parent / 'images' / 'odoo' / 'config' / str(current_version()) / 'requirements.txt'
    click.secho("pip3 install -r {}".format(requirements1))

