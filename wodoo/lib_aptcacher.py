from .tools import create_network

import click

from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
import subprocess
from .tools import abort
from .tools import autocleanpaper


APT_CACHER_CONTAINER_NAME = "apt-cacher"
config_file = "/etc/apt-cacher-ng/acng.conf"


@cli.group(cls=AliasedGroup)
@pass_config
def apt(config):
    pass


def delete_gpg_files():
    start_apt_cacher()
    cmd = "find /var/cache/apt-cacher-ng/ -type f \( -name '*InRelease' -o -name '*Release.gpg' \)"
    subprocess.run(
        ["docker", "exec", APT_CACHER_CONTAINER_NAME, "sh", "-c", cmd]
    )


def _get_apt_cacher_config():
    ancg_conf = (
        subprocess.run(
            [
                "docker",
                "exec",
                APT_CACHER_CONTAINER_NAME,
                "cat",
                config_file,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .splitlines()
    )
    ancg_conf = [
        line.strip()
        for line in ancg_conf
        if line.strip() and not line.startswith("#")
    ]
    return ancg_conf


def start_apt_cacher():
    container_name = APT_CACHER_CONTAINER_NAME
    image_name = "sameersbn/apt-cacher-ng:latest"
    network = "aptcache-net"  # necessary so name resolution works
    port_mapping = "3142:3142"

    def setup_options():
        ancg_conf = _get_apt_cacher_config()
        options = {
            "ExThreshold": "0",
            "PassThroughPattern": [
                ".*apt\.postgres\.org.*",
                ".*apt*.postgresql*.org.*",
                ".*Release$",
                ".*InRelease$",
                ".*Packages$",
                ".*Sources$",
            ],
            "DlMaxRetries": "5",
        }
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
            with autocleanpaper() as tfile:
                tfile.write_text("\n".join(conf) + "\n")

                subprocess.run(
                    [
                        "docker",
                        "cp",
                        tfile,
                        f"{container_name}:{config_file}",
                    ]
                )
                subprocess.run(["docker", "restart", container_name])
        click.secho("\n".join(conf), fg="blue")

    # Check if container is already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={container_name}"],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        setup_options()
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

    setup_options()


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
def show_config(ctx, config):
    conf = _get_apt_cacher_config()
    click.secho("\n".join(conf), fg="green")


@apt.command()
@pass_config
@click.pass_context
def restart(ctx, config):
    subprocess.run(["docker", "restart", APT_CACHER_CONTAINER_NAME])


@apt.command()
@pass_config
@click.pass_context
def gpg_clear(ctx, config):
    delete_gpg_files()
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
