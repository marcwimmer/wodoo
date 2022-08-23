from operator import itemgetter
import subprocess
import arrow
import sys
import shutil
import tempfile
import click
from .tools import __dc
from .tools import search_env_path
from . import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from pathlib import Path
from .tools import abort

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

DOCKER_VOLUMES = Path("/var/lib/docker/volumes")


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


def _get_path(config):
    path = DOCKER_VOLUMES / __get_postgres_volume_name(config)
    return path


def _get_next_snapshotpath(config):
    counter = 0
    while True:
        path = _get_path(config)
        path = Path(str(path) + f".{counter}")
        if not path.exists():
            break
        counter += 1
    return path


def _get_possible_snapshot_paths(path):
    """
    :param path: root path
    """
    yield Path(path)
    yield from Path(path).parent.glob(f"{path.name}.*")


def _get_poolname_of_path(path):
    """
    output of "df -T <path>"
    rpool/ROOT/ubuntu_srb0yj/var/lib/marc1 zfs  1689338880   128 1689338752   1% /var/lib/marc1

    output of df -T /var/lib/marc1/abcdef
    rpool/ROOT/ubuntu_srb0yj/var/lib/marc1 zfs  1689338880   128 1689338752   1% /var/lib/marc1

    Poolname: rpool/ROOT/ubuntu_srb0yj
    """
    while str(path).endswith("/"):
        path = Path(str(path[:-1]))
    if path.exists():
        dfout = subprocess.check_output(["df", "-T", path], encoding="utf8").splitlines()[1]
    else:
        return None
    fullpath, fstype, _, _, _, _, df_path = unify(dfout.strip()).split(" ")
    poolname = str(fullpath).replace(df_path, "")
    assert fullpath.startswith(poolname)

    if df_path != str(path):
        raise NotZFS(
            f"path is not a zfs volume {path}.\n\n{HOWTO_PREPARE}", poolname=poolname
        )
    if fstype != "zfs":
        raise Exception("Not a zfs filesystem")

    return poolname


def __get_postgres_volume_name(config):
    return f"{config.project_name}_odoo_postgres_volume"


def __get_snapshots(config):
    path = _get_path(config)
    try:
        return _get_snapshots(path)
    except NotZFS:
        abort(f"Path {path} is not a zfs.")


def _get_snapshots(path):
    zfs = search_env_path("zfs")
    poolname = _get_poolname_of_path(path)

    def _get_snaps(path):
        for path in _get_possible_snapshot_paths(path):
            for line in (
                subprocess.check_output(
                    ["sudo", zfs, "list", "-t", "snapshot", str(path)],
                    encoding="utf8",
                    stderr=subprocess.DEVNULL,  # ignore output of 'no datasets available'
                )
                .strip()
                .splitlines()[1:]
            ):
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
                info["pool"] = poolname
                info["path"] = snapshotname.replace(poolname, "").split("@")[0]
                yield info
    yield from sorted(_get_snaps(path), key=lambda x: x['date'], reverse=True)


def assert_environment(config):
    pass


def _turn_into_subvolume(path):
    """
    Makes a zfs pool out of a path.
    """
    try:
        _get_poolname_of_path(path)
    except NotZFS as ex:
        zfs = search_env_path("zfs")
        click.secho(f"Turning {path} into a zfs pool.", fg="green")
        filename = path.parent / Path(tempfile.mktemp()).name
        if filename.exists():
            raise Exception(f"Path {filename} should not exist.")
        shutil.move(path, filename)
        try:
            assert str(path).startswith("/")
            subprocess.check_call(["sudo", "mkdir", path])
            fullpath = ex.poolname + str(path)
            subprocess.check_output(["sudo", zfs, "create", fullpath])
            click.secho(
                f"Writing back the files to original position: from {filename}/ to {path}/"
            )
            subprocess.check_call(
                [
                    "sudo",
                    "rsync",
                    str(filename) + "/",
                    str(path) + "/",
                    "-ar",
                ]
            )
        finally:
            subprocess.check_call(["sudo", "rm", "-Rf", filename])
    else:
        return


def make_snapshot(config, name):
    zfs = search_env_path("zfs")
    __dc(["stop", "-t 1"] + ["postgres"])
    path = _get_path(config)
    _turn_into_subvolume(path)
    snapshots = list(_get_snapshots(path))
    snapshot = list(filter(lambda x: x["name"] == name, snapshots))
    if snapshot:
        if config.force:
            subprocess.check_call(["sudo", zfs, "destroy", snapshot[0]["fullpath"]])
        else:
            click.secho(f"Snapshot {name} already exists.", fg="red")
            sys.exit(-1)

    poolname = _get_poolname_of_path(path)
    assert " " not in name
    fullpath = f"{poolname}{path}@{name}"
    subprocess.check_call(["sudo", zfs, "snapshot", fullpath])
    __dc(["up", "-d"] + ["postgres"])
    return name


def restore(config, name):
    zfs = search_env_path("zfs")
    if not name:
        return

    assert "@" not in name
    assert "/" not in name

    path = _get_path(config)
    snapshots = list(_get_snapshots(path))
    default_volume_path = Path(_get_path(config))
    snapshot = list(filter(lambda x: x["name"] == name, snapshots))
    if not snapshot:
        abort(f"Snapshot {name} does not exist.")
    snapshot = snapshot[0]
    snapshots_of_volume = [x for x in snapshots if Path(x['path']) == default_volume_path]
    try:
        index = list(map(lambda x: x['name'], snapshots_of_volume)).index(name)
    except ValueError:
        index = -1

    __dc(["stop", "-t 1"] + ["postgres"])
    if index == 0:
        # restore last one is easy in the volumefolder it self; happiest case
        subprocess.check_call(["sudo", zfs, "rollback", snapshot["fullpath"]])
    else:
        next_path = _get_next_snapshotpath(config)
        poolname = _get_poolname_of_path(snapshot["path"])
        full_next_path = poolname + str(next_path)
        subprocess.check_call(
            ["sudo", zfs, "rename", poolname + str(path), full_next_path]
        )
        subprocess.check_call(
            ["sudo", zfs, "clone", snapshot['fullpath'], poolname + str(path)]
        )
    __dc(["rm", "-f"] + ["postgres"])
    __dc(["up", "-d"] + ["postgres"])


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
        subprocess.check_call(["sudo", zfs, "destroy", snapshot["fullpath"]])


def remove_volume(config):
    zfs = search_env_path("zfs")
    volume_path = _get_path(config)
    pool_name = _get_poolname_of_path(volume_path)
    for path in _get_possible_snapshot_paths(volume_path):
        if not path.exists():
            continue
        subprocess.check_call(["sudo", zfs, "destroy", "-R", pool_name + str(path)])
        click.secho(f"Removed: {path}", fg='yellow')
