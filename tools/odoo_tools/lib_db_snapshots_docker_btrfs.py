from operator import itemgetter
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

DOCKER_VOLUMES = Path("/var/lib/docker/volumes")
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

def _get_btrfs_infos(path):
    import pudb
    pudb.set_trace()
    info = {}
    for line in subprocess.check_output([
            '/usr/bin/btrfs',
            'subvol',
            'show',
            str(path)
    ]).split("\n"):
        for line in infos:
            if 'Creation time:' in line:
                info['date'] = arrow.get(line.split(":", 1)[1].strip()).datetime
    return info

def __get_snapshots(config):
    files = list(_get_subvolume_dir(config).glob("*"))
    snapshots = list({
        'path': str(x),
        'name': x.name,
        'date': _get_btrfs_infos(x)['date'],
    } for x in reversed(files))
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
    _turn_into_subvolume(DOCKER_VOLUMES / __get_postgres_volume_name(config))

    # check if name already exists, and if so abort
    dest_path = path / name
    if dest_path.exists():
        click.secho(f"Path {dest_path} already exists.", fg='red')
        sys.exit(-1)

    subprocess.check_output(
        _get_cmd_butter_volume() + [
            "snapshot",
            "-r", # readonly
            f'{DOCKER_VOLUMES}/{volume_name}',
            str(dest_path),
        ]).decode('utf-8').strip()
    __dc(['up', '-d'] + ['postgres'])
    return name

def restore(config, name):
    if not name:
        return

    if '/' not in str(name):
        name = _get_subvolume_dir(config) / name

    name = Path(name)
    if not name.exists():
        click.secho(f"Path {name} does not exist.", fg='red')
        sys.exit(-1)

    __dc(['stop', '-t 1'] + ['postgres'])
    volume_path = DOCKER_VOLUMES / __get_postgres_volume_name(config)
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
    if snapshot['path'] in map(itemgetter('path'), snapshots):
        subprocess.check_call(
            _get_cmd_butter_volume() + [
                'delete',
                str(snapshot['path']),
            ]
        )
