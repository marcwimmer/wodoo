"""
To be able to do snapshots: the volumes folder must be a child of a zfs filesystem:
zfs create zfs_pool1/docker
zfs create zfs_pool1/docker/volumes


zfs list -o name,usedbychildren     #
docker/vlsa039t563j1yi1k4hum45or                                                0B
docker/volumes                                                                100K
docker/volumes/t1                                                               0B
docker/w0lqy0goq0ylqmt0pipsrjoxt                                                0B
docker/w0v9nokwbqazajfri0u3k5cor                                                0B
better: zfs get -H -o value usedbychildren docker/volumes  mit -1 oder nicht

"""

import inquirer
import time
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
from pathlib import Path
from .tools import abort
from .tools import get_volume_fullpath

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


def docker_volume_path():
    return "/var/lib/docker/volumes"


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


CACHE_ZFS_PATH = None


def check_correct_zfs_setup(config):
    # get mountpoint of zfs pool or zfs
    PATH = docker_volume_path()
    if not __is_zfs_fs(PATH):
        return
    zfspool_or_zfsvolume = _get_zfs_pool_or_zfs_parent(PATH)
    zfspool_mountpath = (
        subprocess.check_output(
            [
                "zfs",
                "get",
                "-H",
                "-o",
                "value",
                "mountpoint",
                zfspool_or_zfsvolume,
            ],
            encoding="utf8",
        )
        .splitlines()[-1]
        .strip()
    )
    relative_path_to_mountpath = Path(PATH).relative_to(zfspool_mountpath)

    if relative_path_to_mountpath.parts:
        abort(
            "\nZFS Misconfiguration detected\n------------------------------------\n"
            "There mustn't be any relative path "
            f'between the zfs pool or parent zfs "{zfspool_or_zfsvolume}" \nand the mountpoint '
            f"{PATH}/somevolume. \n"
            f"To solve this, create a zfs mounted at {PATH} e.g. with \n"
            "zfs create pool1/docker_volumes \n"
            "zfs set compression=on pool1/docker_volumes \n"
            f"zfs set mountpoint={PATH} pool1/docker_volumes \n"
            "\n\n"
            "And restart docker."
        )


def _get_zfs_pool_or_zfs_parent(path):
    try:
        findmnt = subprocess.check_output(
            ["findmnt", "--target", path, "--output", "SOURCE"],
            encoding="utf8",
        ).splitlines()
    except subprocess.CalledProcessError:
        abort(f"No zfs pool found for {path}")
    if not findmnt:
        abort(f"No zfs pool found for {path}")
    zfspool = findmnt[1].strip()
    return zfspool


def _get_zfs_path(config):
    """
    takes the postgresname and translates:
    pg1 --> /var/lib/docker/volumes/pg1 --> /dockervolumes/pg1

    Doesnt matter if pg1 is already a snapshot or not

    """
    global CACHE_ZFS_PATH
    if CACHE_ZFS_PATH is None:
        PATH = docker_volume_path()
        postgresname = __get_postgres_volume_name(config)
        zfspool = _get_zfs_pool_or_zfs_parent(PATH)

        fstype = subprocess.check_output(
            ["findmnt", "--target", PATH, "--output", "FSTYPE"],
            encoding="utf8",
        ).splitlines()
        if fstype[1].strip() != "zfs":
            abort(f"No zfs pool found for {PATH}")

        check_correct_zfs_setup(config)

        # TARGET                  SOURCE        FSTYPE OPTIONS
        # /var/lib/docker/volumes dockervolumes zfs    rw,relatime,xattr,noacl,casesensitive
        CACHE_ZFS_PATH = str(Path(zfspool) / postgresname)
    return CACHE_ZFS_PATH


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
    postgresvolume = __get_postgres_volume_name(config)
    base_path = _get_zfs_path(config)
    if not __is_zfs_fs(Path(base_path).parent):
        abort(f"Not a zfs path: {base_path}")
    snaps = [
        x
        for x in subprocess.check_output(
            [zfs, "list", "-t", "snapshot", "-o", "name"], encoding="utf8"
        ).splitlines()[1:]
    ]

    def matches(path):
        return (
            "/" + postgresvolume + "." in path
            or "/" + postgresvolume + "@" in path
        )

    snaps = list(filter(matches, snaps))
    yield from snaps


def __get_snapshots(config):
    path = _get_path(config)
    try:
        return _get_snapshots(config)
    except NotZFS:
        abort(f"Path {path} is not a zfs.")


def _get_snapshots(config):
    def _get_snaps():
        for path in _get_possible_snapshot_paths(config):
            if "@" not in path:
                continue
            snapshotname = unify(path.split(" "))[0]
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


def __is_zfs_fs(path_zfs):
    path_zfs = str(path_zfs)
    assert " " not in path_zfs
    return _is_zfs_path(path_zfs)


def assert_environment(config):
    pass


def _turn_into_subvolume(config):
    """
    Makes a zfs volume out of a path.
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
        abort(
            f"{fullpath} does not exist. Did you start postgres? (odoo up -d)"
        )

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
                        "continue",
                        message=("Snapshot already exists - overwrite?"),
                    )
                ]
            )
            if not answer["continue"]:
                sys.exit(-1)
        subprocess.check_call(
            ["sudo", zfs, "destroy", snapshot[0]["fullpath"]]
        )

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
            f"Could not umount {zfs_full_path}. Perhaps not a problem.",
            fg="yellow",
        )


def restore(config, name):
    zfs = search_env_path("zfs")
    if not name:
        return

    assert "@" not in name
    assert "/" not in name

    snapshots = list(_get_snapshots(config))
    snapshot = list(filter(lambda x: x["name"] == name, snapshots))
    if not snapshot:
        abort(f"Snapshot {name} does not exist.")
    snapshot = snapshot[0]
    zfs_full_path = _get_zfs_path(config)
    snapshots_of_volume = [
        x
        for x in snapshots
        if x["fullpath"].split("@")[0].startswith(zfs_full_path)
    ]
    try:
        index = list(map(lambda x: x["name"], snapshots_of_volume)).index(name)
    except ValueError:
        index = -1

    __dc(config, ["stop", "-t", "1"] + ["postgres"])
    full_next_path = _get_next_snapshotpath(config)
    _try_umount(config)
    if _is_zfs_path(zfs_full_path):
        subprocess.check_call(
            ["sudo", zfs, "rename", zfs_full_path, full_next_path]
        )
    snap_name = snapshot["fullpath"].split("@")[-1]
    snapshot_path = _get_zfs_path_for_snap_name(config, snap_name)
    __dc(config, ["rm", "-f"] + ["postgres"])
    cmd = [
        "sudo",
        zfs,
        "clone",
        snapshot_path,
        zfs_full_path,
    ]
    subprocess.check_call(cmd)
    click.secho(f"Restore command:")
    click.secho(" ".join(map(str, cmd)), fg="yellow")
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
        subprocess.check_call(
            ["sudo", zfs, "destroy", "-R", snapshot["fullpath"]]
        )
        remount(config)


def remove_volume(config):
    zfs = search_env_path("zfs")
    umount = search_env_path("umount")
    for path in _get_possible_snapshot_paths(config):
        try:
            subprocess.check_call(
                ["sudo", zfs, "set", "canmount=noauto", path]
            )
        except:
            click.secho(
                "Failed to execute canmount=noauto, but perhaps not a problem. Trying to continue.",
                fg="yellow",
            )
        try:
            subprocess.check_call(["sudo", umount, path])
        except:
            pass

        fullpath = (
            translate_poolPath_to_fullPath(Path(path).parent) / Path(path).name
        )
        if fullpath.exists() or "@" in str(fullpath):
            try:
                subprocess.check_call(
                    ["sudo", zfs, "destroy", "-R", path],
                    encoding="utf8",
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )
            except:
                click.secho(
                    f"Failed to destroy zfs dataset at {path}.", fg="red"
                )
                time.sleep(1)
            click.secho(f"Removed: {path}", fg="yellow")
        else:
            click.secho(f"{path} did not exist and so wasn't removed.")
    clear_all(config)


def translate_poolPath_to_fullPath(zfs_path):
    zfs_path = Path(zfs_path)
    removed = []
    while len(zfs_path.parts) >= 1:
        mountpoint = None
        try:
            mountpoint = subprocess.check_output(
                [
                    "sudo",
                    zfs,
                    "get",
                    "mountpoint",
                    "-H",
                    "-o",
                    "value",
                    zfs_path,
                ],
                encoding="utf8",
            ).strip()
        except:
            mountpoint = None
        if mountpoint != "-":
            break
        removed.insert(0, zfs_path.parts[-1])
        zfs_path = Path("/".join(zfs_path.parts[:-1]))
    mountpoint = Path(mountpoint) / "/".join(removed) if mountpoint else None

    return Path(mountpoint) if mountpoint else None


def clear_all(config):
    zfs = search_env_path("zfs")
    zfs_full_path = _get_zfs_path(config)
    _try_umount(config)
    diskpath = translate_poolPath_to_fullPath(zfs_full_path)
    if diskpath and __is_zfs_fs(diskpath):
        subprocess.check_call(["sudo", zfs, "destroy", "-r", zfs_full_path])
