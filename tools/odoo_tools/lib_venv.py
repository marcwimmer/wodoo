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
from .tools import __make_file_executable
from .tools import __assure_gitignore
from .odoo_config import customs_dir
from . import cli, pass_config
from .lib_clickhelpers import AliasedGroup

PROTECTED_PIP_PACKAGES = [
    'lxml', 'python-dateutil', 'requests',
    'greenlet', 'psycopg2', 'pillow',
    'passlib', 'pdftotext', 'gevent',
]

@cli.group(cls=AliasedGroup)
@pass_config
def venv(config):
    pass


@venv.command()
@pass_config
def setup(config):
    dir = customs_dir()
    os.chdir(dir)
    subprocess.check_call(["python3", "-m", "venv", config.dirs['venv'].absolute()])
    install_requirements_in_venv(config)

    print("Further:")
    print("If you need redis: brew install redis")
    print("Advanced mail server with roundcube - todo for marc to make the mail client run in docker isolated")

@venv.command()
@pass_config
def delete(config):
    if config.dirs['venv'].exists():
        shutil.rmtree(config.dirs['venv'])
        click.secho(f"Deleted {config.dirs['venv']}")

@venv.command()
@pass_config
def activate(config):
    click.secho(f"source {config.dirs['venv']}/bin/activate")

def _get_bash_prefix(config):
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
        config.dirs['images'] / 'odoo' / 'bin',
        config.dirs['odoo_tools'],
        venv=config.dirs['venv'],
        customs_dir=customs_dir(),
        dbname=customs_dir().name,
        run_dir=config.dirs['run'],
        out_dir=config.dirs['run_native_out_dir'],
        odoo_data_dir=config.dirs['odoo_data_dir'],
    )

def _make_local_bin_files(config):
    """
    creates odoo config files in ~/.odoo/run/<..>/configs/config_*
    """
    for file in [
        'run.py',
        'debug.py',
        'update_modules.py',
    ]:
        template = _get_bash_prefix(config)
        content = template + '\npython \"$ODOOLIB/{}\" "$@"'.format(file)
        filepath = config.dirs['run_native_bin_dir'] / file.replace('.py', '')
        filepath.write_text(content)
        __make_file_executable(filepath)
        del filepath

    bin_dir = customs_dir() / 'bin'
    if bin_dir.exists():
        bin_dir.unlink()
    bin_dir.symlink_to(config.dirs['run_native_bin_dir'])
    __assure_gitignore(customs_dir() / '.gitignore', 'bin')

def install_requirements_in_venv(config):
    req_files = [
        config.dirs['odoo_home'] / 'requirements.txt',
        customs_dir() / 'odoo' / 'requirements.txt',
        config.dirs['odoo_home'] / 'images' / 'odoo' / 'config' / str(current_version()) / 'requirements.txt',
        config.files['native_collected_requirements_from_modules'],
    ]
    file_content = []
    file_content.append("pip install pip --upgrade")
    file_content.append("pip install pudb")
    file_content.append("brew install geos postgresql zlib pv poppler pkg-config freetype|| true")
    # brew tells about following lines
    file_content.append('export CFLAGS="$CFLAGS -I/usr/local/opt/zlib/include"')
    file_content.append('export LDFLAGS="$LDFLAGS -L/usr/local/opt/zlib/lib"')
    file_content.append('export CPPFLAGS="$CPPFLAGS -I/usr/local/opt/zlib/include"')
    file_content.append("pip3 install cython wheel setuptools watchdog")
    # filter out lxml; problematic on venv and macos
    req_files_dir = config.dirs['run_native_requirements']
    for i, req_file in enumerate(req_files):
        # filter out some packages
        filename = req_files_dir / f"{i}.txt"
        content = req_file.read_text().split("\n")
        content = [x for x in content if all(y not in x for y in PROTECTED_PIP_PACKAGES)]
        filename.parent.mkdir(exist_ok=True, parents=True)
        filename.write_text('\n'.join(content))
        file_content.append("pip install -r '{}'".format(filename))
        del filename
    for pip in PROTECTED_PIP_PACKAGES:
        file_content.append(f"pip install {pip} --upgrade")

    config.files['native_bin_install_requirements'].parent.mkdir(exist_ok=True, parents=True)
    config.files['native_bin_install_requirements'].write_text(_get_bash_prefix(config) + "\n" + '\n'.join(file_content))
    __make_file_executable(config.files['native_bin_install_requirements'])
    subprocess.call([config.files['native_bin_install_requirements']])

    click.secho((
        f"The following pip packages were taken from system and were not touched:"
        f"{', '.join(PROTECTED_PIP_PACKAGES)}"
    ), fg='green')
