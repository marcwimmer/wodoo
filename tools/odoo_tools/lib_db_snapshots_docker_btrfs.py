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

def __get_postgres_volume_name(config):
    return config.PROJECT_NAME + "_" + 'ODOO_POSTGRES_VOLUME'


def _get_cmd_butter_volume():
    # 12.12.2020 Docker version 20.10.0, build 7287ab3
    # Docker version installed and running with the container simply does not work,
    # because that container does not start. Using the buttervolume pypi plugin works,
    # so switching to that.
    # buttervolume==3.7
    # sudoer entry:
    ## Cmnd_Alias BUTTERVOLUME = /usr/bin/runc --root /run/docker/plugins/runtime-root/plugins.moby/ *
    ## odoo-xxxxx ALL=(ALL) NOPASSWD: BUTTERVOLUME
    #drunc = ["sudo", "runc", "--root", "/run/docker/plugins/runtime-root/plugins.moby/"]
    #container_id = subprocess.check_output(drunc + ["list"]).decode('utf-8').split('\n')[1].split(" ")[0]
    # buttervolume = drunc + ['exec', '-t', container_id, 'buttervolume']
    return ["sudo", "/usr/local/bin/buttervolume"]

@cli.group(cls=AliasedGroup)
@pass_config
def snapshot(config):
    pass

def __assert_btrfs(config):
    if not config.run_btrfs:
        click.echo("Please enable RUN_BTRFS=1 and make sure, that volumes are using the anybox/buttervolume docker plugin")
        sys.exit(-1)

def __get_snapshots(config):
    snapshots = [x for x in subprocess.check_output(_get_cmd_butter_volume() + ["snapshots"]).decode('utf-8').split("\n") if x]
    # filter to current customs
    name = __get_postgres_volume_name(config)
    snapshots = [x for x in snapshots if name in x in x]
    return snapshots

def _try_get_date_from_snap(snap_name):
    try:
        snap_name = snap_name.split("@")[-1][:19]
        d = datetime.strptime(snap_name, '%Y-%m-%dT%H:%M:%S')
        tz = os.getenv("TZ", "")
        if tz:
            d = arrow.get(d).to(tz).datetime
        return d
    except Exception:
        return None

def assert_environment(config):
    __assert_btrfs(config)

def make_snapshot(config, name):
    volume_name = __get_postgres_volume_name(config)
    __dc(['stop', '-t 1'] + ['postgres'])
    snapshot_name = subprocess.check_output(_get_cmd_butter_volume() + ["snapshot", volume_name]).decode('utf-8').strip()
    __dc(['up', '-d'] + ['postgres'])
    return snapshot_name

def restore(config, name):
    if not name:
        return
    __dc(['stop', '-t 1'] + ['postgres'])
    subprocess.check_call(_get_cmd_butter_volume() + ["restore", name])

    __dc(['up', '-d'] + ['postgres'])

def remove(config, snapshot):
    snapshots = __get_snapshots(config)
    if snapshot in snapshots:
        __dc(['stop', '-t 1'] + ['postgres'])
        subprocess.check_call(_get_cmd_butter_volume() + ["rm", snapshot])
        __dc(['up', '-d'] + ['postgres'])
    values = config.__get_snapshot_db(config)
    if snapshot in values:
        del values[snapshot]
        config.__set_snapshot_db(config, values)
