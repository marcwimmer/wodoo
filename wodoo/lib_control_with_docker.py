import sys
import shutil
import os
import click
from .tools import __dcrun
from .tools import _askcontinue
from .tools import _is_container_running
from .tools import _get_bash_for_machine
from .tools import __cmd_interactive
from .tools import _display_machine_tips
from .tools import _wait_postgres
from .tools import __replace_in_file
from .tools import _wait_for_port
from .tools import __dcexec
from .tools import __dc
from .tools import __dc_out
from .tools import _get_host_ip
from .tools import __needs_docker
import subprocess
from .cli import Commands


def _get_volume_hostpath(volume):
    from pathlib import Path

    path = Path(
        subprocess.check_output(
            [
                "/usr/bin/sudo",
                "/usr/bin/docker",
                "volume",
                "inspect",
                "--format",
                "{{ .Mountpoint }}",
                volume,
            ]
        )
        .decode("utf-8")
        .strip()
    )
    if path.name == "_data":
        path = path.parent
    return path


def _get_volume_size(volume):
    try:
        size = subprocess.check_output(
            [
                "/usr/bin/sudo",
                "/usr/bin/du",
                "-sh",
                _get_volume_hostpath(volume),
            ]
        ).decode("utf-8")
        size = size.split("\t")[0]
        return size
    except Exception:
        return "n/a"


def _start_postgres_before(config):
    __dc(config, ["up", "-d", "postgres"])
    _wait_postgres(config)


def dev(ctx, config, build, kill):
    """
    starts developing in the odoo container
    """
    from .myconfigparser import MyConfigParser

    myconfig = MyConfigParser(config.files["settings"])
    if not config.devmode and not config.force:
        click.echo("Requires dev mode.")
        sys.exit(-1)
    if build:
        build(ctx, config)
    if kill:
        click.echo("Killing all docker containers")
        do_kill(ctx, config, machines=[], brutal=True)
        rm(ctx, config, machines=[])
    _start_postgres_before(config)
    __dc(config, ["up", "-d"])
    Commands.invoke(ctx, "kill", machines=["odoo"])
    ip = _get_host_ip()
    proxy_port = myconfig["PROXY_PORT"]
    roundcube_port = myconfig["ROUNDCUBE_PORT"]
    click.secho(
        "Proxy Port: http://{}:{}".format(ip, proxy_port),
        fg="green",
        bold=True,
    )
    click.secho(
        "Mailclient : http://{}:{}".format(ip, roundcube_port),
        fg="green",
        bold=True,
    )

    # execute script
    ScriptFile = config.files["start-dev"]
    if not ScriptFile.exists():
        click.secho(
            f"Info: you may provide a startup script here: {ScriptFile}",
            fg="yellow",
        )
    else:
        FNULL = open(os.devnull, "w")
        subprocess.Popen([ScriptFile], shell=True, stdout=FNULL)

    Commands.invoke(ctx, "debug", machine="odoo")


def ps(config):
    args = ["ps", "-a"]
    __dc(config, args)


def execute(config, machine, args):
    args = [machine] + list(args)
    __dcexec(config, args)


def get_all_running_containers(config, profiles=None):
    cmd = ["ps"]
    output = __dc_out(
        config, cmd + ["--format", "table {{.Service}}"], profile=profiles
    ).strip()
    return output.splitlines()[1:]


def do_kill(ctx, config, machines=[], brutal=False, profile="auto"):
    """
    kills running machine
    safely shutdowns postgres and redis

    if not brutal it means softly
    """
    SAFE_KILL = []

    if not brutal:
        for machine in (config.safe_kill or "").split(","):
            if getattr(config, "run_{}".format(machine)):
                SAFE_KILL.append(machine)

    machines = list(machines)
    if not machines:
        machines = get_all_running_containers(config, profiles=profile)
    safe_stop = []
    for machine in SAFE_KILL:
        if not machines or machine in machines:
            if _is_container_running(config, machine):
                safe_stop += [machine]

    if safe_stop:
        __dc(
            config, ["stop", "-t", "20"] + safe_stop, profile=profile
        )  # persist data
    try:
        if brutal:
            __dc(config, ["kill"] + list(machines), profile=profile)
        else:
            __dc(config, ["stop", "-t", "2"] + list(machines), profile=profile)
    except subprocess.CalledProcessError as e:
        pass
        # was not possible to handle the not running error
        # chat gpt also suggests to maximally handle no such container or container not running


def force_kill(ctx, config, machine, profile="auto"):
    do_kill(ctx, config, machine=machine, brutal=True, profile=profile)


def wait_for_container_postgres(config):
    if config.USE_DOCKER:
        _wait_postgres(config)


def wait_for_port(host, port):
    port = int(port)
    _wait_for_port(host=host, port=port)


def recreate(ctx, config, machines=[]):
    machines = list(machines)
    __dc(config, ["up", "--no-start", "--force-recreate"] + machines)


def up(
    ctx, config, machines=[], daemon=False, remove_orphans=True, profile="all"
):
    machines = list(machines)
    from .consts import resolve_profiles

    options = [
        # '--remove-orphans', # lost data with that; postgres volume suddenly new after rm?
        #'--compatibility' # to support reousrce limit swarm mode
    ]
    if daemon:
        options += ["-d"]
    if remove_orphans:
        options += ["--remove-orphans"]
    dc_options = []
    if not machines and config.run_postgres and daemon and config.USE_DOCKER:
        _start_postgres_before(config)
    for profile in resolve_profiles(profile):
        dc_options2 = dc_options + ["--profile", profile]
        __dc(config, dc_options2 + ["up"] + options + machines)


def down(ctx, config, machines=[], volumes=False, remove_orphans=True):
    machines = list(machines)

    options = []
    # '--remove-orphans', # lost data with that; postgres volume suddenly new after rm?
    if volumes:
        options += ["--volumes"]
    if remove_orphans:
        options += ["--remove-orphans"]
    if config.devmode:
        __dc(config, ["kill"] + machines)

    __dc(config, ["down"] + options + machines)

    if volumes:
        Commands.invoke(ctx, "remove-volumes")


def stop(ctx, config, machines=[]):
    do_kill(ctx, config, machines=machines)


def rebuild(ctx, config, machines=[]):
    Commands.invoke(ctx, "compose", customs=config.customs)
    build(ctx, config, machines=machines, no_cache=True)


def restart(ctx, config, machines=[], profile="auto", brutal=True):
    machines = list(machines)

    # this is faster than docker restart: tested with normal project 6.75 seconds vs. 4.8 seconds
    do_kill(ctx, config, machines=machines, profile=profile, brutal=brutal)
    up(ctx, config, machines=machines, daemon=True, profile=profile)


def rm(ctx, config, machines=[], profile="auto"):
    __needs_docker(config)
    machines = list(machines)
    __dc(config, ["rm", "-f"] + machines, profile=profile)


def attach(ctx, config, machine):
    """
    attaches to running machine
    """
    __needs_docker(config)
    _display_machine_tips(config, machine)
    bash = _get_bash_for_machine(machine)
    __cmd_interactive(config, "exec", machine, bash)


def pull(ctx, config):
    __dc(config, ["pull"])


def build(
    ctx,
    config,
    machines=[],
    pull=False,
    no_cache=False,
    push=False,
    include_source=False,
    platform=None,
):
    """
    no parameter all machines, first parameter machine name and passes other params; e.g. ./odoo build asterisk --no-cache"
    """
    options = []
    if pull:
        options += ["--pull"]
    if no_cache:
        options += ["--no-cache"]
        # if "--pull" not in options:
        #     # options += ["--pull"]
        #     pass
        # error with wodoo src image

    if config.verbose:
        os.environ["BUILDKIT_PROGRESS"] = "plain"

    if include_source:
        raise NotImplementedError("Please implement include source.")

    if not platform:
        platform = subprocess.check_output(
            ["/usr/bin/uname", "-m"], encoding="utf8"
        ).strip()
    # options += ["--platform", platform]

    # update wodoo src before:
    subprocess.run(
        ["docker", "buildx", "build", "-t", "wodoo_src", "."],
        cwd=config.dirs["images"] / "wodoo",
        check=True,
    )

    # if platform:
    #     import pudb;pudb.set_trace()
    #     options += ["--platform", platform]

    __dc(
        config,
        ["build"] + options + list(machines),
        env={
            "ODOO_VERSION": config.odoo_version,
            "DOCKER_DEFAULT_PLATFORM": f"linux/{platform}",
            "DOCKER_BUILDKIT": "1",
            "COMPOSE_BAKE": "true",
        },
    )


def debug(ctx, config, machine, ports, cmd=None):
    """
    starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
    """
    # puts endless loop into container command and then attaches to it;
    # by this, name resolution to the container still works
    if not config.devmode:
        _askcontinue(
            config,
            "Current machine {} is dropped and restartet with service ports in bash. Usually you have to type /debug.sh then.".format(
                machine
            ),
        )
    # shutdown current machine and start via run and port-mappings the replacement machine
    do_kill(ctx, config, machines=[machine])
    rm(ctx, config, machines=[machine])
    src_files = [config.files["debugging_template_onlyloop"]]
    if ports:
        src_files += [config.files["debugging_template_withports"]]

    cmd_prefix = []
    for i, filepath in enumerate(src_files):
        dest = config.files["debugging_composer"]
        dest = dest.parent / dest.name.replace(".yml", ".{}.yml".format(i))
        shutil.copy(filepath, dest)
        __replace_in_file(dest, "__PORT__", ports or "33284")
        __replace_in_file(dest, "${NAME}", machine)
        __replace_in_file(
            dest, "${DOCKER_COMPOSE_VERSION}", config.YAML_VERSION
        )

        # TODO make configurable in machines
        PORT = str({"odoo": 8069, "odoo_debug": 8069}.get(machine, 80))
        __replace_in_file(dest, "{machine_main_port}", PORT)

        cmd_prefix += ["-f", dest]

    __dc(config, cmd_prefix + ["up", "-d", machine])
    if not cmd:
        attach(ctx, config, machine=machine)
    else:
        __dcexec(config, [machine, cmd], interactive=True)


def run(ctx, config, machine, args, **kwparams):
    """
    extract volume mounts

    """
    if args and args[0] == "bash" and len(args) == 1:
        runbash(ctx, config, machine=machine)
        return
    __dcrun(config, [machine] + list(args), **kwparams)


def runbash(ctx, config, machine, args, **kwparams):
    _display_machine_tips(config, machine)
    bash = _get_bash_for_machine(machine)
    cmd = ["run", "--rm", "--entrypoint", "", machine]
    if args:
        cmd += args
    else:
        cmd += [bash]
    __cmd_interactive(config, *tuple(cmd))


def logall(config, machines, follow, lines):
    cmd = ["logs"]
    if follow:
        cmd += ["-f"]
    if lines:
        cmd += [f"--tail={lines}"]
    cmd += list(machines)
    __dc(config, cmd)


def shell(config, command="", queuejobs=False):
    if os.getenv("DOCKER_MACHINE") == "1":
        cmdline = ["/odoolib/entrypoint.sh", "/odoolib/shell.py"]
        if command:
            cmdline += [command]
        subprocess.run(cmdline)
        return
    cmd = [
        "run",
        "--rm",
        "-it",
        "-e",
        "TERM=xterm-256color",
        "-e",
        "PYTHONUNBUFFERED=1",
        "odoo",
        "/odoolib/shell.py",
    ]
    if queuejobs:
        cmd += ["--queuejobs"]
    __cmd_interactive(config, *(cmd + [command]))
