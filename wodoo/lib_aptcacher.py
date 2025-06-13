from pathlib import Path
from .tools import create_network
import json

import click
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
import subprocess
from .tools import abort
from .tools import remove_comments
from .tools import docker_get_file_content
from .tools import copy_into_docker


APT_CACHER_CONTAINER_NAME = "apt-cacher"
config_file = "/etc/apt-cacher-ng/acng.conf"


@cli.group(cls=AliasedGroup)
@pass_config
def apt(config):
    pass


def delete_gpg_files(config):
    start_apt_cacher(config)
    cmd = "find /var/cache/apt-cacher-ng/ -type f \( -name '*InRelease' -o -name '*Release.gpg' \)"
    subprocess.run(
        ["docker", "exec", APT_CACHER_CONTAINER_NAME, "sh", "-c", cmd]
    )


def _get_apt_cacher_config():
    return remove_comments(
        docker_get_file_content(APT_CACHER_CONTAINER_NAME, config_file)
    )


def update_ancg_conf(config):
    ancg_conf = _get_apt_cacher_config()
    options = json.loads(
        (config.dirs["images"] / "apt_cacher" / "acng.conf").read_text()
    )
    conf = []
    for line in ancg_conf:
        if any(line.startswith(f"{option}: ") for option in options):
            continue
        conf.append(line)
    for option, value in options.items():
        if not isinstance(value, list):
            value = [value]
        for value in value:
            conf.append(f"{option}: {value}")
    if ancg_conf != conf:
        copy_into_docker(
            "\n".join(conf) + "\n", APT_CACHER_CONTAINER_NAME, config_file
        )
        subprocess.run(["docker", "restart", APT_CACHER_CONTAINER_NAME])
    click.secho("\n".join(ancg_conf), fg="blue")


def update_mirrors(config):
    changed = False
    for file in (config.dirs["images"] / "apt_cacher").glob("*"):
        if str(file).endswith(".orig"):
            continue
        filepath_docker = Path("/usr/lib/apt-cacher-ng") / file.name
        try:
            content = docker_get_file_content(
                APT_CACHER_CONTAINER_NAME, filepath_docker
            )
        except:
            content = []
        newcontent = file.splitlines()
        if newcontent != content:
            copy_into_docker(
                "\n".join(newcontent) + "\n",
                APT_CACHER_CONTAINER_NAME,
                filepath_docker,
            )
            changed = True

    if changed:
        subprocess.run(["docker", "restart", APT_CACHER_CONTAINER_NAME])


def start_apt_cacher(config):
    container_name = APT_CACHER_CONTAINER_NAME
    image_name = "sameersbn/apt-cacher-ng:latest"
    network = "aptcache-net"  # necessary so name resolution works
    port_mapping = "3142:3142"

    # Check if container is already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={container_name}"],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        update_ancg_conf(config)
        click.secho(f"Container '{container_name}' is already running.")
        return

    create_network(network)

    # If not running, start it
    result = subprocess.run(
        ["docker", "ps", "-q", "-a", "-f", f"name={container_name}"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if result:
        cmd = [
            "docker",
            "start",
            result,
        ]
    else:
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--network",
            network,
            "-p",
            port_mapping,
            image_name,
        ]
    click.secho(f"Starting container '{container_name}'...", fg="blue")

    try:
        subprocess.run(cmd, check=True)
        click.secho(
            f"Container '{container_name}' started on port 3142.", fg="green"
        )
    except subprocess.CalledProcessError as e:
        abort(str(e))

    update_ancg_conf(config)


@apt.command()
@pass_config
@click.pass_context
def attach(ctx, config):
    subprocess.run(
        ["docker", "exec", "-it", APT_CACHER_CONTAINER_NAME, "bash"]
    )


@apt.command()
@pass_config
@click.pass_context
def aptconfig(ctx, config):
    conf = _get_apt_cacher_config()
    click.secho("\n".join(conf), fg="green")


@apt.command()
@pass_config
@click.pass_context
def aptrestart(ctx, config):
    subprocess.run(["docker", "restart", APT_CACHER_CONTAINER_NAME])


@apt.command()
@pass_config
@click.pass_context
def gpg_clear(ctx, config):
    delete_gpg_files(config)
    click.secho("Deleted GPG files in apt-cacher-ng cache", fg="green")


@apt.command(help="ls /var/cache/apt/apt-cacher-ng")
@click.argument("cache", nargs=-1)
@pass_config
@click.pass_context
def clear(ctx, config, cache):
    # Check if container is already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={APT_CACHER_CONTAINER_NAME}"],
        capture_output=True,
        text=True,
    )
    containerid = result.stdout.strip()
    if not containerid:
        click.secho(f"Container '{APT_CACHER_CONTAINER_NAME}' is not running.")
        return
    if not cache:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                containerid,
                "find",
                "/var/cache/apt-cacher-ng/",
                "-maxdepth",
                "1",
                "-type",
                "d",
                "-printf",
                "%f\n",
            ],
            capture_output=True,
            text=True,
        )
        options = []
        for line in result.stdout.splitlines()[1:]:
            if line.strip() in ["_xstore", "var"]:
                continue
            options.append(line)
        import inquirer

        todelete = inquirer.prompt(
            [
                inquirer.List(
                    "filename", "Choose cache to delete", choices=options
                )
            ]
        )["filename"]
        if not todelete:
            abort("No cache selected, aborting.")
        todelete = [todelete]

    else:
        todelete = cache
    for cache in todelete:
        subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                containerid,
                "rm",
                "-Rf",
                "/var/cache/apt-cacher-ng/{cache}",
            ],
            capture_output=True,
            text=True,
        )
        click.secho(
            f"Removed cache {cache} from {APT_CACHER_CONTAINER_NAME}",
            fg="green",
        )
    click.secho("Stopping apt proxy...", fg="green")
    subprocess.run(["docker", "kill", containerid])


@apt.command()
@pass_config
@click.pass_context
def reset(ctx, config):
    click.secho("Removing apt cacher with volumes.")
    subprocess.run(["docker", "rm", "-f", APT_CACHER_CONTAINER_NAME])
