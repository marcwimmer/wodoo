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
from .tools import get_volume_fullpath, get_docker_volumes

SNAPSHOT_DIR = get_docker_volumes() / 'subvolumes'


def _get_path(config):
    return get_volume_fullpath(__get_postgres_volume_name(config))


def _get_cmd_butter_volume():
    return ["sudo", search_env_path("btrfs"), "subvolume"]


def __assert_btrfs(config):
    # TODO check if volumes of docker is in a subvolume
    pass


def _get_subvolume_dir(config):
    subvolume_dir = SNAPSHOT_DIR / __get_postgres_volume_name(config)
    if not subvolume_dir.exists():
        subprocess.check_call(
            [
                "sudo",
                "mkdir",
                "-p",
                subvolume_dir,
            ]
        )
    return subvolume_dir


def _get_btrfs_infos(path):
    info = {}
    for line in (
        subprocess.check_output(
            ["sudo", search_env_path("btrfs"), "subvol", "show", str(path)]
        )
        .decode("utf-8")
        .split("\n")
    ):
        if "Creation time:" in line:
            line = line.split(":", 1)[1].strip()
            line = " ".join(line.split(" ")[:2])
            info["date"] = arrow.get(line).datetime
    return info


def __get_snapshots(config):
    files = list(_get_subvolume_dir(config).glob("*"))
    snapshots = list(
        {
            "path": str(x),
            "name": x.name,
            "date": _get_btrfs_infos(x)["date"],
        }
        for x in reversed(files)
    )
    return snapshots


def assert_environment(config):
    __assert_btrfs(config)


def _turn_into_subvolume(path):
    """
    Makes a subvolume out of a path. Docker restart required?
    """
    process = subprocess.Popen(
        ["sudo", search_env_path("btrfs"), "subvolume", "show", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    std_out, std_err = process.communicate()
    if process.returncode != 0:
        err_msg = std_err.decode("utf-8").lower()
        if any(
            x.lower() in err_msg for x in ["Not a Btrfs subvolume", "not a subvolume"]
        ):
            click.secho(f"Turning {path} into a subvolume.")
            filename = path.parent / Path(tempfile.mktemp()).name
            if filename.exists():
                raise Exception(f"Path {filename} should not exist.")
            shutil.move(path, filename)
            try:
                subprocess.check_output(["sudo", "btrfs", "subvolume", "create", path])
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
            raise Exception("Unexpected error at turning into subvolume")
    else:
        return


def make_snapshot(ctx, config, name):
    __dc(config, ["stop", "-t 1"] + ["postgres"])
    path = _get_subvolume_dir(config)
    _turn_into_subvolume(_get_path(config))

    # check if name already exists, and if so abort
    dest_path = path / name
    if dest_path.exists():
        if config.force:
            remove(config, name)
        else:
            click.secho(f"Path {dest_path} already exists.", fg="red")
            sys.exit(-1)

    subprocess.check_output(
        _get_cmd_butter_volume()
        + [
            "snapshot",
            "-r",  # readonly
            _get_path,
            str(dest_path),
        ]
    ).decode("utf-8").strip()
    __dc(config, ["up", "-d"] + ["postgres"])
    return name


def restore(config, name):
    if not name:
        return

    if "/" not in str(name):
        name = _get_subvolume_dir(config) / name

    name = Path(name)
    if not name.exists():
        click.secho(f"Path {name} does not exist.", fg="red")
        sys.exit(-1)

    __dc(config, ["stop", "-t 1"] + ["postgres"])
    volume_path = _get_path(config)
    if volume_path.exists():
        subprocess.check_call(
            _get_cmd_butter_volume()
            + [
                "delete",
                volume_path,
            ]
        )
    subprocess.check_call(
        _get_cmd_butter_volume() + ["snapshot", name, str(volume_path)]
    )

    __dc(config, ["rm", "-f"] + ["postgres"])
    __dc(config, ["up", "-d"] + ["postgres"])


def remove(config, snapshot):
    snapshots = __get_snapshots(config)
    if isinstance(snapshot, str):
        snapshots = [x for x in snapshots if x["name"] == snapshot]
        if not snapshots:
            click.secho(f"Snapshot {snapshot} not found!", fg="red")
            sys.exit(-1)
        snapshot = snapshots[0]
    if snapshot["path"] in map(itemgetter("path"), snapshots):
        subprocess.check_call(
            _get_cmd_butter_volume()
            + [
                "delete",
                str(snapshot["path"]),
            ]
        )


def purge_inactive(config):
    for vol in SNAPSHOT_DIR.glob("*"):
        if not vol.is_dir():
            continue
        try:
            next(get_docker_volumes().glob(vol.name))
        except StopIteration:
            for snapshot in vol.glob("*"):
                click.secho(f"Deleting snapshot {snapshot}", fg="red")
                subprocess.check_call(
                    ["sudo", "btrfs", "subvolume", "delete", str(snapshot)]
                )
            click.secho(f"Deleting {vol}", fg="red")
            shutil.rmtree(vol)
