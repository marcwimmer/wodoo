from .tools import create_network

import click
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
import subprocess
from .tools import abort
import inquirer


APT_CACHER_CONTAINER_NAME = "squid-deb-proxy"
PROXPI_CONTAINER_NAME = "proxpi-cacher"


@cli.group(cls=AliasedGroup)
@pass_config
def cache(config):
    pass


def start_container(
    config, container_name, image_name, build_path, network, port_mapping
):
    # Check if container is already running
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={container_name}"],
        capture_output=True,
        text=True,
    )

    def update():
        return
        update_acng_conf(config)
        update_mirrors(config)

    if result.stdout.strip():
        update()
        click.secho(f"Container '{container_name}' is already running.")
        return

    create_network(network)
    cmd = ["docker", "build", "-t", image_name, "."]
    subprocess.run(cmd, check=True, cwd=config.dirs["images"] / "apt_cacher")

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
            f"Container '{container_name}' started on port {port_mapping}.",
            fg="green",
        )
    except subprocess.CalledProcessError as e:
        abort(str(e))

    update()


def start_squid_proxy(config):
    image_name = "squid-deb-cacher-wodoo"
    start_container(
        config,
        APT_CACHER_CONTAINER_NAME,
        image_name,
        config.dirs["images"] / "apt_cacher",
        network="aptcache-net",
        port_mapping="3142:8000",
    )


def start_proxpi(config):
    image_name = "epicwink/proxpi"
    start_container(
        config,
        PROXPI_CONTAINER_NAME,
        image_name,
        None,
        network="proxpi-net",
        port_mapping="3143:8000",
    )


@cache.command()
@pass_config
@click.pass_context
def apt_attach(ctx, config):
    subprocess.run(
        ["docker", "exec", "-it", APT_CACHER_CONTAINER_NAME, "bash"]
    )


@cache.command()
@pass_config
@click.pass_context
def proxpi_attach(ctx, config):
    subprocess.run(["docker", "exec", "-it", PROXPI_CONTAINER_NAME, "bash"])


@cache.command()
@pass_config
@click.pass_context
def apt_restart(ctx, config):
    subprocess.run(["docker", "restart", APT_CACHER_CONTAINER_NAME])


@cache.command()
@pass_config
@click.pass_context
def pypi_restart(ctx, config):
    subprocess.run(["docker", "restart", PROXPI_CONTAINER_NAME])


@cache.command()
@pass_config
@click.pass_context
def apt_reset(ctx, config):
    click.secho("Removing squid deb proxy with volumes.")
    subprocess.run(["docker", "rm", "-f", APT_CACHER_CONTAINER_NAME])


@cache.command()
@pass_config
@click.pass_context
def pypi_reset(ctx, config):
    click.secho("Removing proxpi with volumes.")
    subprocess.run(["docker", "rm", "-f", PROXPI_CONTAINER_NAME])


@cache.command()
@pass_config
@click.pass_context
def setup(ctx, config):
    from .tools import get_local_ips, choose_ip, is_interactive
    from .cli import Commands

    ips = list(sorted(get_local_ips()))
    ip = choose_ip(ips)
    if not is_interactive():
        abort("Please define system wide APT_PROXY_IP")

    questions = [
        inquirer.Text(
            "apt_port",
            message="Enter APT proxy port",
            default="3142",
            validate=lambda _, x: x.isdigit()
            and 1 <= int(x) <= 65535
            or "Must be a valid port number",
        ),
        inquirer.Text(
            "pypi_port",
            message="Enter PyPI proxy port",
            default="3143",
            validate=lambda _, x: x.isdigit()
            and 1 <= int(x) <= 65535
            or "Must be a valid port number",
        ),
    ]

    answers = inquirer.prompt(questions)

    apt_proxy = f"{ip}:{answers['apt_port']}"
    pypi_proxy = f"{ip}:{answers['pypi_port']}"
    Commands.invoke(
        ctx, "setting", name="APT_PROXY_IP", value=apt_proxy, no_reload=True
    )
    Commands.invoke(
        ctx, "setting", name="PIP_PROXY_IP", value=pypi_proxy, no_reload=False
    )
