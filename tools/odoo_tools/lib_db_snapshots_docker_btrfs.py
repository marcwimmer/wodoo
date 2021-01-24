import subprocess
import yaml
import arrow
import json
import pipes
import re
import traceback
import sys
import shutil
import hashlib
import os
import tempfile
import click
import inquirer
from datetime import datetime
from .tools import remove_webassets
from .tools import _askcontinue
from .tools import __dc
from .tools import get_volume_names
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password
from pathlib import Path

SNAPSHOT_DIR = Path("/var/lib/docker/subvolumes")

def __get_postgres_volume_name(config):
    return f"{config.project_name}_odoo_postgres_volume"

def _get_cmd_butter_volume():
    return ["sudo", "/usr/bin/btrfs", "subvolume"]

@cli.group(cls=AliasedGroup)
@pass_config
def snapshot(config):
    pass

def __assert_btrfs(config):
    # TODO check if volumes of docker is in a subvolume
    pass

def _get_subvolume_dir(config):
    subvolume_dir = SNAPSHOT_DIR / __get_postgres_volume_name(config)
    if not subvolume_dir.exists():
        subprocess.check_call([
            'sudo',
            'mkdir',
            '-p',
            subvolume_dir,
        ])
    return subvolume_dir

def __get_snapshots(config):
    snapshots = list(reversed(list(_get_subvolume_dir(config).glob("*"))))
    return snapshots

def assert_environment(config):
    __assert_btrfs(config)

def _turn_into_subvolume(path):
    """
    Makes a subvolume out of a path. Docker restart required?
    """
    process = subprocess.Popen(['sudo', 'btrfs', 'subvolume', 'show', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = process.communicate()
    if process.returncode != 0:
        if 'Not a Btrfs subvolume' in std_err.decode('utf-8'):
            click.secho(f"Turning {path} into a subvolume.")
            filename = tempfile.mktemp(suffix='.')
            subprocess.check_call(['sudo', '/usr/bin/mv', path, filename])
            try:
                subprocess.check_output(['sudo', 'btrfs', 'subvolume', 'create', path])
                click.secho("Writing back the files to original position")
                subprocess.check_call([
                    'sudo',
                    'rsync',
                    str(filename) + '/',
                    str(path) + '/',
                    '-ar',
                ])
            finally:
                subprocess.check_call(['sudo', 'rm', '-Rf', filename])
        else:
            raise
    else:
        return

def make_snapshot(config, name):
    volume_name = __get_postgres_volume_name(config)
    __dc(['stop', '-t 1'] + ['postgres'])
    path = _get_subvolume_dir(config)
    _turn_into_subvolume(Path('/var/lib/docker/volumes') / __get_postgres_volume_name(config))

    snapshot_name = f"{name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.check_output(
        _get_cmd_butter_volume() + [
            "snapshot",
            "-r", # readonly
            f'/var/lib/docker/volumes/{volume_name}',
            str(path / snapshot_name),
        ]).decode('utf-8').strip()
    __dc(['up', '-d'] + ['postgres'])
    return snapshot_name

def restore(config, name):
    if not name:
        return
    __dc(['stop', '-t 1'] + ['postgres'])
    volume_path = Path("/var/lib/docker/volumes") / __get_postgres_volume_name(config)
    if volume_path.exists():
        subprocess.check_call(
            _get_cmd_butter_volume() + [
                'delete',
                volume_path,
            ]
        )
    subprocess.check_call(
        _get_cmd_butter_volume() + [
            'snapshot',
            name,
            str(volume_path)
        ]
    )

    __dc(['rm', '-f'] + ['postgres'])
    __dc(['up', '-d'] + ['postgres'])

def remove(config, snapshot):
    snapshots = __get_snapshots(config)
    if snapshot in snapshots:
        subprocess.check_call(
            _get_cmd_butter_volume() + [
                'delete',
                str(snapshot),
            ]
        )
