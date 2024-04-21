"""
To work the volumes folder must be a child of a zfs filesystem:
zfs create zfs_pool1/docker
zfs create zfs_pool1/docker/volumes

set /etc/odoo/settings ZFS_PATH_VOLUMES=zfs_pool1/docker/volumes  then


zfs list -o name,usedbychildren     # 
docker/vlsa039t563j1yi1k4hum45or                                                0B
docker/volumes                                                                100K
docker/volumes/t1                                                               0B
docker/w0lqy0goq0ylqmt0pipsrjoxt                                                0B
docker/w0v9nokwbqazajfri0u3k5cor                                                0B
better: zfs get -H -o value usedbychildren docker/volumes  mit -1 oder nicht

"""

import inquirer
from .tools import abort
from operator import itemgetter
import subprocess
import arrow
import sys
import shutil
import tempfile
import click
from .tools import __dc
from .tools import search_env_path, __get_postgres_volume_name
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from pathlib import Path
from .tools import abort
from .tools import get_volume_fullpath, verbose

MAX_I = 500

HOWTO_PREPARE = """

Preperation docker - be careful - make backups

systemctl stop docker
mv /var/lib/docker /var/lib/docker.old
mkdir -p /var/lib/docker/volumes
zfs create -p rpool/.../var/lib/docker/volumes
rsync /var/lib/docker.old/ /var/lib/docker/ -arP
rm -Rf /var/lib/docker.old
systemctl start docker

"""

try:
    zfs = search_env_path("zfs")
except Exception:
    zfs = None


class NotZFS(Exception):
    def __init__(self, msg, poolname):
        super().__init__(msg)
        self.poolname = poolname


def unify(text):
    while "\t" in text:
        text = text.replace("\t", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def _is_zfs_path(path):
    """
    path e.g. tankdocker/volumes/postgres1
    """
    try:
        subprocess.check_output(
            ["sudo", zfs, "list", str(path)],
            encoding="utf8",
            stderr=subprocess.DEVNULL,  # ignore output of 'no datasets available'
        ).strip().splitlines()[1:]
        return True
    except subprocess.CalledProcessError:
        return False


def _get_path(config):
    return get_volume_fullpath(__get_postgres_volume_name(config))


def _get_zfs_path(config):
    """
    takes the postgresname and translates:
    pg1 --> /var/lib/docker/volumes/pg1

    Doesnt matter if pg1 is already a snapshot or not

    """
    datasets = _get_all_mountpoints()
    viceversa = {v: k for k, v in datasets.items()}
    postgresname = __get_postgres_volume_name(config)
    firstmatch = [x for x in datasets.values() if x.endswith("/" + postgresname)]
    secondmatch = [x for x in datasets.values() if x.endswith("/volumes")]
    if firstmatch:
        return viceversa[firstmatch[0]]
    if secondmatch:
        return viceversa[secondmatch[0]] + "/" + postgresname
    raise Exception(f"Not found: {postgresname} in {','.join(datasets.keys())}")


def _get_next_snapshotpath(config):
    counter = 0
    while True:
        path = _get_zfs_path(config)
        path = str(path) + f".{counter}"
        if not __is_zfs_fs(path):
            break
        counter += 1
    return path


def _get_possible_snapshot_paths(config):
    """
    :param path: root path
    """
    # TODO
    # all_zfs_folders = _get_all_zfs()
    base_path = _get_zfs_path(config)
    for i in range(-1, MAX_I):
        if i == -1:
            if _is_zfs_path(base_path):
                yield from _call_list_snapshots(base_path)
        else:
            path = f"{base_path}.{i}"
            if _is_zfs_path(path):
                yield from _call_list_snapshots(path)


def __get_snapshots(config):
    path = _get_path(config)
    try:
        return _get_snapshots(config)
    except NotZFS:
        abort(f"Path {path} is not a zfs.")


def _call_list_snapshots(path):
    res = (
        subprocess.check_output(
            ["sudo", zfs, "list", "-t", "snapshot", str(path)],
            encoding="utf8",
            stderr=subprocess.DEVNULL,  # ignore output of 'no datasets available'
        )
        .strip()
        .splitlines()[1:]
    )
    res = list(map(lambda x: x.split()[0], res))
    return res


def _get_snapshots(config):
    def _get_snaps():
        for path in _get_possible_snapshot_paths(config):
            for line in _call_list_snapshots(path):
                snapshotname = unify(line.split(" "))[0]
                creation = unify(
                    subprocess.check_output(
                        ["sudo", zfs, "get", "-p", "creation", snapshotname],
                        encoding="utf8",
                    )
                    .strip()
                    .splitlines()[1]
                )
                _, _, timestamp, _ = creation.split(" ")
                timestamp = arrow.get(int(timestamp)).datetime
                info = {}
                info["date"] = timestamp
                info["fullpath"] = snapshotname
                info["name"] = snapshotname.split("@")[1]
                info["path"] = snapshotname.split("/")[-1]
                yield info

    yield from sorted(_get_snaps(), key=lambda x: x["date"], reverse=True)


_cache = {}


def _get_all_zfs():
    datasets = _get_all_mountpoints()
    return datasets.keys()


def __is_zfs_fs(path_zfs):
    path_zfs = str(path_zfs)
    assert " " not in path_zfs
    return _is_zfs_path(path_zfs)
    datasets = _get_all_zfs()
    return str(path_zfs) in datasets


def assert_environment(config):
    pass


def _turn_into_subvolume(config):
    """
    Makes a zfs pool out of a path.
    """
    if config.NAMED_ODOO_POSTGRES_VOLUME:
        abort("Not compatible with NAMED_ODOO_POSTGRES_VOLUME by now.")
    zfs = search_env_path("zfs")
    fullpath = _get_path(config)
    fullpath_zfs = _get_zfs_path(config)
    if __is_zfs_fs(fullpath_zfs):
        # is zfs - do nothing
        return

    filename = fullpath.parent / Path(tempfile.mktemp()).name
    if filename.exists():
        raise Exception(f"Path {filename} should not exist.")
    if not fullpath.exists():
        abort(f"{fullpath} does not exist. Did you start postgres? (odoo up -d)")

    shutil.move(fullpath, filename)
    try:
        subprocess.check_output(["sudo", zfs, "create", fullpath_zfs])
        click.secho(
            f"Writing back the files to original position: from {filename}/ to {fullpath}/"
        )
        subprocess.check_call(
            [
                "sudo",
                "rsync",
                str(filename) + "/",
                str(fullpath) + "/",
                "-ar",
                "--info=progress2",
            ]
        )
    finally:
        subprocess.check_call(["sudo", "rm", "-Rf", filename])


def make_snapshot(ctx, config, name):
    zfs = search_env_path("zfs")
    __dc(config, ["stop", "-t", "1"] + ["postgres"])
    _turn_into_subvolume(config)
    snapshots = list(_get_snapshots(config))
    snapshot = list(filter(lambda x: x["name"] == name, snapshots))
    if snapshot:
        if not config.force:
            answer = inquirer.prompt(
                [
                    inquirer.Confirm(
                        "continue", message=("Snapshot already exists - overwrite?")
                    )
                ]
            )
            if not answer["continue"]:
                sys.exit(-1)
        subprocess.check_call(["sudo", zfs, "destroy", snapshot[0]["fullpath"]])

    assert " " not in name
    fullpath = _get_zfs_path(config) + "@" + name
    subprocess.check_call(["sudo", zfs, "snapshot", fullpath])
    __dc(config, ["up", "-d"] + ["postgres"])
    return name


def remount(config):
    zfs_full_path = _get_zfs_path(config)
    zfs = search_env_path("zfs")
    subprocess.check_call(
        ["sudo", zfs, "mount", zfs_full_path],
    )


def _try_umount(config):
    zfs_full_path = _get_zfs_path(config)
    umount = search_env_path("umount")
    try:
        subprocess.check_call(
            ["sudo", umount, zfs_full_path],
        )
    except subprocess.CalledProcessError:
        click.secho(
            f"Could not umount {zfs_full_path}. Perhaps not a problem.", fg="yellow"
        )


def restore(config, name):
    zfs = search_env_path("zfs")
    if not name:
        return

    assert "@" not in name
    assert "/" not in name

    zfs_full_path = _get_zfs_path(config)

    __dc(config, ["stop", "-t", "1"] + ["postgres"])
    dst = translate_poolPath_to_fullPath(zfs_full_path)
    for path in [dst]:
        if not path.exists():
            abort(f"{path} missing!")

    snapshot_full_path = translate_poolPath_to_fullPath(zfs_full_path + "@" + name)

    temp_mount_path = Path("/mnt") / str(snapshot_full_path).split("/")[-1]
    if temp_mount_path.exists():
        try:
            verbose(f"Unmounting {temp_mount_path}")
            subprocess.run(["sudo", "umount", temp_mount_path])
        except Exception:
            pass
    else:
        temp_mount_path.mkdir(exist_ok=True, parents=True)
        # subprocess.run(["sudo", "chattr", "+i", temp_mount_path])
    verbose(f"Mounting {temp_mount_path}")
    subprocess.run(
        ["sudo", "mount", "-t", "zfs", snapshot_full_path, temp_mount_path],
    )
    try:
        click.secho(f"Copying data from {temp_mount_path} to {dst}", fg="blue")
        subprocess.run(
            [
                "sudo",
                "rsync",
                str(temp_mount_path) + "/",
                str(dst) + "/",
                "-ar",
                "--info=progress2",
                # "--delete-after",
            ],
        )
    finally:
        verbose(f"Unmounting {temp_mount_path}...")
        # subprocess.run(["sudo", "chattr", "-i", temp_mount_path])
        subprocess.run(["sudo", "umount", temp_mount_path])
        subprocess.run(["sudo", "rm", "-Rf", temp_mount_path])
    __dc(config, ["rm", "-f"] + ["postgres"])
    __dc(config, ["up", "-d"] + ["postgres"])


def _get_zfs_path_for_snap_name(config, snap_name):
    for path in _get_possible_snapshot_paths(config):
        if path.split("@")[-1] == snap_name:
            return path
    abort(f"Could not find snapshot with name {snap_name}")


def remove(config, snapshot):
    zfs = search_env_path("zfs")
    snapshots = __get_snapshots(config)
    if isinstance(snapshot, str):
        snapshots = [x for x in snapshots if x["name"] == snapshot]
        if not snapshots:
            click.secho(f"Snapshot {snapshot} not found!", fg="red")
            sys.exit(-1)
        snapshot = snapshots[0]
    if snapshot["fullpath"] in map(itemgetter("fullpath"), snapshots):
        _try_umount(config)
        subprocess.check_call(["sudo", zfs, "destroy", "-R", snapshot["fullpath"]])
        remount(config)


def remove_volume(config):
    zfs = search_env_path("zfs")
    umount = search_env_path("umount")
    for path in _get_possible_snapshot_paths(config):
        try:
            subprocess.check_call(["sudo", zfs, "set", "canmount=noauto", path])
        except:
            click.secho(
                "Failed to execute canmount=noauto, but perhaps not a problem. Trying to continue.",
                fg="yellow",
            )
        try:
            subprocess.check_call(["sudo", umount, path])
        except:
            pass
        subprocess.check_call(["sudo", zfs, "destroy", "-R", path])
        click.secho(f"Removed: {path}", fg="yellow")
    clear_all(config)


def translate_poolPath_to_fullPath(zfs_path):
    zfs_path = Path(zfs_path)
    removed = []
    while len(zfs_path.parts) > 1:
        mountpoint = subprocess.check_output(
            ["sudo", zfs, "get", "mountpoint", "-H", "-o", "value", zfs_path],
            encoding="utf8",
        ).strip()
        if mountpoint != "-":
            break
        removed.insert(0, zfs_path.parts[-1])
        zfs_path = Path("/".join(zfs_path.parts[:-1]))
    mountpoint = Path(mountpoint) / "/".join(removed)

    return Path(mountpoint)


def clear_all(config):
    zfs = search_env_path("zfs")
    zfs_full_path = _get_zfs_path(config)
    _try_umount(config)
    diskpath = translate_poolPath_to_fullPath(zfs_full_path)
    if __is_zfs_fs(diskpath):
        subprocess.check_call(["sudo", zfs, "destroy", "-r", zfs_full_path])


# ----------------------------------
def _get_all_mountpoints():
    if "datasets" not in _cache:
        zfs = search_env_path("zfs")

        lines = subprocess.check_output(
            ["sudo", zfs, "list", "-o", "name,mountpoint"], encoding="utf8"
        ).splitlines()
        lines = list(filter(lambda x: not x.strip().endswith("legacy"), lines[1:]))
        datasets = {}
        for line in lines:
            dataset, path = line.split()
            datasets[dataset] = path.strip()
        _cache["datasets"] = datasets
    return _cache["datasets"]
