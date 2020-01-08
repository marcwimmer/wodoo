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
from .tools import __make_file_executable
from .tools import __assure_gitignore
from .odoo_config import current_customs
from .odoo_config import customs_dir
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from . import PROJECT_NAME

@cli.group(cls=AliasedGroup)
@pass_config
def venv(config):
    pass


@venv.command()
@pass_config
def setup(config):
    dir = customs_dir()
    os.chdir(dir)
    subprocess.check_call(["python3", "-m", "venv", dirs['venv'].absolute()])
    install_requirements_in_venv(config)

def _get_bash_prefix():
    return """#!/bin/bash
set -e
set +x
export ODOOLIB="{0}"
export ODOO_USER="$(whoami)"
export ODOO_DATA_DIR="{odoo_data_dir}"
export SERVER_DIR="{customs_dir}/odoo"
export PYTHONPATH="{1}"
export RUN_DIR="{run_dir}"
export NO_SOFFICE=1
export OUT_DIR="{out_dir}"
export INTERNAL_ODOO_PORT=8069
source "{venv}/bin/activate"

""".format(
        dirs['images'] / 'odoo' / 'bin',
        dirs['odoo_tools'],
        venv=dirs['venv'],
        customs_dir=customs_dir(),
        dbname=customs_dir().name,
        run_dir=dirs['run'],
        out_dir=dirs['run_native_out_dir'],
        odoo_data_dir=dirs['odoo_data_dir'],
    )

def _make_local_bin_files():
    """
    creates odoo config files in ~/.odoo/run/<..>/configs/config_*
    """
    for file in [
        'run.py',
        'debug.py',
        'update_modules.py',
    ]:
        template = _get_bash_prefix()
        content = template + '\npython \"$ODOOLIB/{}\" "$@"'.format(file)
        filepath = dirs['run_native_bin_dir'] / file.replace('.py', '')
        filepath.write_text(content)
        __make_file_executable(filepath)
        del filepath

    bin_dir = customs_dir() / 'bin'
    if bin_dir.exists():
        bin_dir.unlink()
    bin_dir.symlink_to(dirs['run_native_bin_dir'])
    __assure_gitignore(customs_dir() / '.gitignore', 'bin')

def install_requirements_in_venv(config):
    req_files = [
        dirs['odoo_home'] / 'requirements.txt',
        customs_dir() / 'odoo' / 'requirements.txt',
        dirs['odoo_home'] / 'images' / 'odoo' / 'config' / str(current_version()) / 'requirements.txt'
    ]
    file_content = []
    file_content.append("pip install pip --upgrade")
    file_content.append("pip install pudb")
    file_content.append("brew install postgresql zlib pv poppler || true")
    # brew tells about following lines
    file_content.append('export CFLAGS="$CFLAGS -I/usr/local/opt/zlib/include"')
    file_content.append('export LDFLAGS="$LDFLAGS -L/usr/local/opt/zlib/lib"')
    file_content.append('export CPPFLAGS="$CPPFLAGS -I/usr/local/opt/zlib/include"')
    file_content.append("pip3 install cython")
    file_content.append("pip3 install watchdog")
    for req_file in req_files:
        file_content.append("pip install -r '{}'".format(req_file))
    files['native_bin_install_requirements'].parent.mkdir(exist_ok=True, parents=True)
    files['native_bin_install_requirements'].write_text(_get_bash_prefix() + "\n" + '\n'.join(file_content))
    __make_file_executable(files['native_bin_install_requirements'])
    subprocess.call([files['native_bin_install_requirements']])
