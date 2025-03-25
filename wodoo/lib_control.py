import time
import click

import re
import os
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import execute_script
from .tools import force_input_hostname
import subprocess
from .tools import abort
from .tools import ensure_project_name
from .tools import print_prod_env


@cli.group(cls=AliasedGroup)
@pass_config
def docker(config):
    pass


@docker.command()
@pass_config
@click.pass_context
def pull(ctx, config):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import pull as lib_pull
    return lib_pull(ctx, config)


@docker.command()
@click.option("-b", "--build", is_flag=True)
@click.option("-k", "--kill", is_flag=True)
@pass_config
@click.pass_context
def dev(ctx, config, build, kill):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import dev as lib_dev
    return lib_dev(ctx, config, build, kill=kill)


@docker.command(name="ps")
@pass_config
def ps(config):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import ps as lib_ps
    return lib_ps(config)


@docker.command(name="exec")
@click.argument("machine", required=True)
@click.argument("args", nargs=-1)
@pass_config
def execute(config, machine, args):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import execute as lib_execute
    lib_execute(config, machine, args)


@docker.command(name="kill")
@click.argument("machines", nargs=-1)
@click.option("-b", "--brutal", is_flag=True, help="dont wait")
@click.option("-p", "--profile")
@pass_config
@click.pass_context
def do_kill(ctx, config, machines, brutal, profile):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import do_kill as lib_do_kill

        lib_do_kill(ctx, config, machines, brutal=False, profile=profile)


@docker.command()
@click.option("-d", "--dry-run", is_flag=True)
@pass_config
@click.pass_context
def remove_volumes(ctx, config, dry_run):
    """
    Experience: docker-compose down -v lets leftovers since june/2023
    At restore everything must be cleaned up.
    """
    ensure_project_name(config)
    if not config.devmode:
        if not config.force:
            abort("Please provide force option on non dev systems")
    if not config.use_docker:
        return
    subprocess.check_call(["sync"])
    volumes = _get_project_volumes(config)
    for vol in volumes:
        click.secho(f"Removing: {vol}", fg="red")
        if not dry_run:
            rc = subprocess.run(
                ["docker", "volume", "rm", "-f", vol],
                encoding="utf8",
                capture_output=True,
            )
            if rc.returncode:
                output = rc.stderr
                for group in re.findall(r"(\[[^\]]*])", output):
                    container_id = group[1:-1]
                    subprocess.run(["docker", "kill", container_id])
                    subprocess.check_call(
                        ["docker", "rm", "-fv", container_id]
                    )
                    counter = 0
                    while counter < 5:
                        try:
                            output = subprocess.check_output(
                                ["docker", "volume", "rm", "-f", vol],
                                encoding="utf8",
                            )
                            break
                        except:
                            click.secho(
                                f"Removing the volume {vol} failed - waiting and retrying.",
                                fg="red",
                            )
                            time.sleep(2)
                            counter += 1

        if dry_run:
            click.secho("Dry Run - didnt do it.")


@docker.command()
@pass_config
@click.pass_context
def force_kill(ctx, config, machine):
    if config.use_docker:
        from .lib_control_with_docker import force_kill as lib_force_kill
    lib_force_kill(ctx, config, machine)


@docker.command()
@pass_config
def wait_for_container_postgres(config):
    if config.use_docker:
        from .lib_control_with_docker import (
            wait_for_container_postgres as lib_wait_for_container_postgres,
        )

        lib_wait_for_container_postgres(config)


@docker.command()
@pass_config
def wait_for_port(config, host, port):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import wait_for_port as lib_wait_for_port
    lib_wait_for_port(host, port)


@docker.command()
@click.argument("machines", nargs=-1)
@pass_config
@click.pass_context
def recreate(ctx, config, machines):
    ensure_project_name(config)
    if config.use_docker:
        from .lib_control_with_docker import recreate as lib_recreate
    lib_recreate(ctx, config, machines)


@docker.command()
@click.argument("machines", nargs=-1)
@click.option("-d", "--daemon", is_flag=True)
@pass_config
@click.pass_context
def up(ctx, config, machines, daemon):
    ensure_project_name(config)
    from .lib_setup import _status
    from .lib_control_with_docker import up as lib_up

    lib_up(ctx, config, machines, daemon, remove_orphans=True)
    execute_script(
        config,
        config.files["after_up_script"],
        "Possible after up script here:",
    )
    if daemon:
        _status(config)


@docker.command()
@click.argument("machines", nargs=-1)
@click.option("-v", "--volumes", is_flag=True)
@click.option("--remove-orphans", is_flag=True)
@click.option("--postgres-volume", is_flag=True)
@pass_config
@click.pass_context
def down(ctx, config, machines, volumes, remove_orphans, postgres_volume):
    ensure_project_name(config)
    from .lib_control_with_docker import down as lib_down
    from .lib_db_snapshots_docker_zfs import NotZFS

    if not config.devmode:
        if not config.force:
            abort("Please provide force option on non live systems")

    print_prod_env(config)

    if not config.devmode and volumes:
        force_input_hostname()

    if postgres_volume or volumes:
        if postgres_volume:
            if not config.force:
                abort("Please use force when call with postgres volume")
        lib_down(ctx, config, machines, volumes=False, remove_orphans=False)
        try:
            Commands.invoke(ctx, "remove_postgres_volume")
        except NotZFS:
            pass

    lib_down(ctx, config, machines, volumes, remove_orphans)


@docker.command()
@click.argument("machines", nargs=-1)
@pass_config
@click.pass_context
def stop(ctx, config, machines):
    ensure_project_name(config)
    from .lib_control_with_docker import stop as lib_stop

    lib_stop(ctx, config, machines)


@docker.command()
@click.argument("machines", nargs=-1)
@pass_config
@click.pass_context
def rebuild(ctx, config, machines):
    ensure_project_name(config)
    from .lib_control_with_docker import rebuild as lib_rebuild

    lib_rebuild(ctx, config, machines)


@docker.command()
@click.argument("machines", nargs=-1)
@click.option("-p", "--profile", default="auto")
@pass_config
@click.pass_context
def restart(ctx, config, machines, profile):
    ensure_project_name(config)
    from .lib_control_with_docker import restart as lib_restart

    lib_restart(ctx, config, machines, profile=profile)


@docker.command()
@click.argument("machines", nargs=-1)
@click.option("-p", "--profile", default="auto")
@pass_config
@click.pass_context
def rm(ctx, config, machines, profile):
    ensure_project_name(config)
    from .lib_control_with_docker import rm as lib_rm

    lib_rm(ctx, config, machines, profile=profile)


@docker.command()
@click.argument("machine", required=True)
@pass_config
@click.pass_context
def attach(ctx, config, machine):
    ensure_project_name(config)
    from .lib_control_with_docker import attach as lib_attach

    lib_attach(ctx, config, machine)


@docker.command()
@click.argument("machines", nargs=-1)
@click.option("--no-cache", is_flag=True)
@click.option("--pull", is_flag=True)
@click.option("--push", is_flag=True)
@click.option("-p", "--plain", is_flag=True)
@click.option("-s", "--include-source", is_flag=True)
@click.option("-rm", "--remove", is_flag=True)
@pass_config
@click.pass_context
def build(
    ctx, config, machines, pull, no_cache, push, plain, include_source, remove
):
    import yaml

    ensure_project_name(config)
    if plain:
        os.environ["BUILDKIT_PROGRESS"] = "plain"
    from .lib_control_with_docker import build as lib_build

    if not machines:
        compose = yaml.safe_load(config.files["docker_compose"].read_text())
        machines = []
        for service in compose["services"]:
            if not compose["services"][service].get("build", {}).get("imgage"):
                machines.append(service)

    lib_build(
        ctx, config, machines, pull, no_cache, push, include_source, remove
    )


@docker.command()
@click.argument("machine", required=True)
@click.option("-c", "--command", required=False, help="Like /odoolib/debug.py")
@click.option("-p", "--ports", is_flag=True, help="With Port 33284")
@click.option("--port", help="Define the debug port")
@pass_config
@click.pass_context
def debug(ctx, config, machine, ports, command, port):
    ensure_project_name(config)
    from .lib_control_with_docker import debug as lib_debug

    if port:
        ports = int(port)

    lib_debug(ctx, config, machine, ports=port, cmd=command)


@cli.command()
@click.argument("machine", required=True)
@click.argument("args", nargs=-1)
@click.option("-d", "--detached", is_flag=True)
@click.option("-n", "--name")
@pass_config
@click.pass_context
def run(ctx, config, machine, detached, name, args, **kwparams):
    ensure_project_name(config)
    from .lib_control_with_docker import run as lib_run

    lib_run(
        ctx, config, machine, args, detached=detached, name=name, **kwparams
    )


@cli.command()
@click.argument("machine", required=True)
@click.argument("args", nargs=-1)
@pass_config
@click.pass_context
def runbash(ctx, config, machine, args, **kwparams):
    ensure_project_name(config)
    from .lib_control_with_docker import runbash as lib_runbash

    lib_runbash(ctx, config, machine, args, **kwparams)


@cli.command(name="logs")
@click.argument("machines", nargs=-1)
@click.option("-n", "--lines", required=False, type=int, default=200)
@click.option("-f", "--follow", is_flag=True)
@pass_config
def logall(config, machines, follow, lines):
    ensure_project_name(config)
    from .lib_control_with_docker import logall as lib_logall

    lib_logall(config, machines, follow, lines)


@docker.command()
@click.argument("command", nargs=-1)
@click.option(
    "-q",
    "--queuejobs",
    is_flag=True,
    help=("Dont delay queuejobs / execute queuejob code"),
)
@pass_config
def shell(config, command, queuejobs):
    print_prod_env(config)

    ensure_project_name(config)
    command = "\n".join(command)
    from .lib_control_with_docker import shell as lib_shell

    lib_shell(config, command, queuejobs)


# problem with stdin: debug then display missing
# @docker.command()
# @click.argument("id", required=True)
# @click.option("-q", "--queuejobs", is_flag=True, help=(
#     "Dont delay queuejobs / execute queuejob code"))
# @pass_config
# def queuejob(config, id, queuejobs):
#     if config.use_docker:
#         from .lib_control_with_docker import shell as lib_shell
#     command = (
#         f"env['queue.job'].browse({id}).run_now()"
#     )
#     lib_shell(command, queuejobs)


def _get_project_volumes(config):
    ensure_project_name(config)
    import yaml

    compose = yaml.safe_load(config.files["docker_compose"].read_text())
    full_volume_names = []
    for volume in compose["volumes"]:
        full_volume_names.append(f"{config.project_name}_{volume}")
    system_volumes = subprocess.check_output(
        ["docker", "volume", "ls"], encoding="utf8"
    ).splitlines()[1:]
    system_volumes = [x.split(" ")[-1] for x in system_volumes]
    system_volumes = [x for x in system_volumes if "_" in x]  # named volumes
    system_volumes = [
        x for x in system_volumes if x.startswith(config.project_name + "_")
    ]

    full_volume_names = list(
        filter(lambda x: x in system_volumes, full_volume_names)
    )
    return full_volume_names


@docker.command()
@click.option("-f", "--filter")
@pass_config
def show_volumes(config, filter):
    from tabulate import tabulate
    from .lib_control_with_docker import _get_volume_size

    volumes = _get_project_volumes(config)
    if filter:
        volumes = [x for x in volumes if filter in x]
    recs = []
    for volume in volumes:
        size = _get_volume_size(volume)
        recs.append((volume, size))
    click.echo(tabulate(recs, ["Volume", "Size"]))


@docker.command()
@click.option("-a", "--show-all", is_flag=True)
@click.option("-f", "--filter")
@click.option("-B", "--no-backup", is_flag=True)
@pass_config
@click.pass_context
def transfer_volume_content(context, config, show_all, filter, no_backup):
    import inquirer
    from pathlib import Path
    from .lib_control_with_docker import _get_volume_size
    from .lib_control_with_docker import _get_volume_hostpath

    volumes = (
        subprocess.check_output(["docker", "volume", "ls"])
        .decode("utf-8")
        .split("\n")[1:]
    )
    volumes = [x.split(" ")[-1] for x in volumes]
    volumes = [x for x in volumes if "_" in x]  # named volumes

    if filter:
        volumes = [x for x in volumes if filter in x]

    def add_size(volume):
        size = _get_volume_size(volume)
        return f"{volume} [{size}]"

    if show_all:
        volumes = list(map(add_size, volumes))
        volumes_filtered_to_project = [
            x for x in volumes if config.project_name in x
        ]

        volumes1 = volumes
        volumes2 = volumes_filtered_to_project

    else:
        volumes_filtered_to_project = [
            x for x in volumes if config.project_name in x
        ]
        volumes_filtered_to_project = list(
            map(add_size, volumes_filtered_to_project)
        )

        volumes1 = volumes_filtered_to_project
        volumes2 = volumes_filtered_to_project

    questions = [
        inquirer.List(
            "volume",
            message="Select source:".format(config.customs, config.dbname),
            choices=volumes1,
        ),
    ]
    answers = inquirer.prompt(questions)
    if not answers or not answers["volume"]:
        return

    source = answers["volume"]
    volumes2.pop(volumes2.index(source))
    questions = [
        inquirer.List(
            "volume",
            message="Select Destination:".format(
                config.customs, config.dbname
            ),
            choices=volumes2,
        ),
    ]
    answers = inquirer.prompt(questions)
    if not answers or not answers["volume"]:
        return
    source = _get_volume_hostpath(source.split(" [")[0])
    dest = _get_volume_hostpath(answers["volume"].split(" [")[0])

    tasks = []
    tasks.append(f"rsync -ar --delete-after {source.name} to {dest.name}")
    for i, task in enumerate(tasks):
        click.secho(f"{i}. {task}")
    answer = inquirer.prompt(
        [inquirer.Confirm("continue", message=("Continue?"))]
    )
    if not answer["continue"]:
        return
    Commands.invoke(context, "down")

    if not no_backup:
        click.secho("Rsyncing files to /tmp as backup...")
        backup_name = str(Path("/tmp/") / dest.name) + ".bak"
        subprocess.check_call(
            [
                "/usr/bin/sudo",
                "rsync",
                "-ar",
                str(dest / "_data") + "/",
                backup_name + "/",
            ]
        )
        click.secho(f"Made backup in {backup_name}")

    click.secho(f"Rsyncing files from old source to {dest}")

    command = [
        "rsync",
        "-arP",
        "--delete-after",
        str(source / "_data") + "/",
        str(dest / "_data") + "/",
    ]
    subprocess.check_call(
        [
            "/usr/bin/sudo",
        ]
        + command
    )


@docker.command()
@pass_config
@click.pass_context
def docker_sizes(context, config):
    from .tools import __dc_out
    from tabulate import tabulate

    output = __dc_out(config, ["config"]).decode("utf-8")
    # docker-compose config | grep "image:" | awk '{print $2}'
    # docker images --format "{{.Repository}}:{{.Tag}} Size: {{.Size}}"
    import yaml

    image_names = list(
        map(
            lambda x: f"{config.project_name}_{x}",
            yaml.safe_load(output)["services"].keys(),
        )
    )
    out = (
        subprocess.check_output(
            [
                "docker",
                "images",
                "--format",
                "{{.Repository}}:{{.Tag}}\tSize: {{.Size}}",
            ]
        )
        .decode("utf8")
        .splitlines()
    )
    sizes = {}
    for line in out:
        name, size = line.split(":", 1)
        size = size.split("\t")[-1]
        sizes[name] = size
    recs = []
    for name in sorted(image_names, key=lambda x: x[0]):
        recs.append((name, sizes.get(name, "")))

    click.echo(tabulate(recs, ["Image Name", "Size"]))


Commands.register(run)
Commands.register(runbash)
Commands.register(do_kill, "kill")
Commands.register(up)
Commands.register(wait_for_container_postgres)
Commands.register(build)
Commands.register(rm)
Commands.register(recreate)
Commands.register(debug)
Commands.register(restart)
Commands.register(shell, "odoo-shell")
Commands.register(down)
Commands.register(stop)
Commands.register(remove_volumes, "remove-volumes")
