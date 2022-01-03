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
from .tools import search_env_path
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password
from pathlib import Path

DOCKER_VOLUMES = Path("/var/lib/docker/volumes")
SNAPSHOT_DIR = Path("/var/lib/docker/subvolumes")

def __get_postgres_volume_name(config):
    return f"{config.project_name}_odoo_postgres_volume"

def _get_cmd_butter_volume():
    return ["sudo", search_env_path('btrfs'), "subvolume"]

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
    info = {}
    for line in subprocess.check_output([
            'sudo',
            search_env_path('btrfs'),
            'subvol',
            'show',
            str(path)
    ]).decode('utf-8').split("\n"):
        if 'Creation time:' in line:
            line = line.split(":", 1)[1].strip()
            line = " ".join(line.split(" ")[:2])
            info['date'] = arrow.get(line).datetime
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
    process = subprocess.Popen(['sudo', search_env_path('btrfs'), 'subvolume', 'show', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = process.communicate()
    if process.returncode != 0:
        err_msg = std_err.decode('utf-8').lower()
        if any(x.lower() in err_msg for x in ['Not a Btrfs subvolume', 'not a subvolume']):
            click.secho(f"Turning {path} into a subvolume.")
            filename = path.parent / Path(tempfile.mktemp()).name
            shutil.move(path, filename)
            try:
                subprocess.check_output(['sudo', 'btrfs', 'subvolume', 'create', path])
                click.secho(f"Writing back the files to original position: from {filename}/ to {path}/")
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
    if isinstance(snapshot, str):
        snapshots = [x for x in snapshots if x['name'] == snapshot]
        if not snapshots:
            click.secho(f"Snapshot {snapshot} not found!", fg='red')
            sys.exit(-1)
        snapshot = snapshots[0]
    if snapshot['path'] in map(itemgetter('path'), snapshots):
        subprocess.check_call(
            _get_cmd_butter_volume() + [
                'delete',
                str(snapshot['path']),
            ]
        )