import platform
import sys
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __dcrun
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import _askcontinue
from .tools import __get_odoo_commit
from .tools import _is_container_running
from .tools import _get_bash_for_machine
from .tools import __cmd_interactive
from .tools import _display_machine_tips
from .tools import _wait_postgres
from .tools import __replace_in_file
from .tools import _wait_for_port
from .tools import __dcexec
from .tools import _get_machines
from .tools import __dc
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
        "Proxy Port: http://{}:{}".format(ip, proxy_port), fg="green", bold=True
    )
    click.secho(
        "Mailclient : http://{}:{}".format(ip, roundcube_port), fg="green", bold=True
    )

    # execute script
    ScriptFile = config.files["start-dev"]
    if not ScriptFile.exists():
        click.secho(
            f"Info: you may provide a startup script here: {ScriptFile}", fg="yellow"
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


def do_kill(ctx, config, machines=[], brutal=False, profile="auto"):
    """
    kills running machine
    safely shutdowns postgres and redis

    if not brutal it means softly
    """
    SAFE_KILL = []

    for machine in (config.safe_kill or "").split(","):
        if getattr(config, "run_{}".format(machine)):
            SAFE_KILL.append(machine)

    machines = list(machines)
    if not brutal and not config.devmode:
        safe_stop = []
        for machine in SAFE_KILL:
            if not machines or machine in machines:
                if _is_container_running(config, machine):
                    safe_stop += [machine]

        if safe_stop:
            __dc(config, ["stop", "-t", "20"] + safe_stop, profile=profile)  # persist data
    if config.devmode:
        __dc(config, ["kill"] + list(machines), profile=profile)
    else:
        __dc(config, ["stop", "-t", "2"] + list(machines), profile=profile)


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


def up(ctx, config, machines=[], daemon=False, remove_orphans=True, profile="auto"):
    machines = list(machines)

    options = [
        # '--remove-orphans', # lost data with that; postgres volume suddenly new after rm?
        #'--compatibility' # to support reousrce limit swarm mode
    ]
    if daemon:
        options += ["-d"]
    if remove_orphans:
        options += ["--remove-orphans"]
    dc_options = []
    if profile:
        dc_options += ["--profile", profile]

    if not machines and config.run_postgres and daemon and config.USE_DOCKER:
        _start_postgres_before(config)
    __dc(config, dc_options + ["up"] + options + machines)


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


def restart(ctx, config, machines=[]):
    machines = list(machines)

    do_kill(ctx, config, machines=machines)
    up(ctx, config, machines=machines, daemon=True)


def rm(ctx, config, machines=[]):
    __needs_docker(config)
    machines = list(machines)
    __dc(config, ["rm", "-f"] + machines)


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
    remove=False,
):
    """
    no parameter all machines, first parameter machine name and passes other params; e.g. ./odoo build asterisk --no-cache"
    """
    options = []
    if pull:
        options += ["--pull"]
    if remove:
        options += ["--force-rm"]
    if no_cache:
        options += ["--no-cache"]
        if "--pull" not in options:
            options += ["--pull"]

    if config.verbose:
        os.environ["BUILDKIT_PROGRESS"] = "plain"

    if include_source:
        raise NotImplementedError("Please implement include source.")

    __dc(
        config,
        ["build"] + options + list(machines),
        env={
            "ODOO_VERSION": config.odoo_version,  # at you developer: do not mismatch with build args
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
        __replace_in_file(dest, "${DOCKER_COMPOSE_VERSION}", config.YAML_VERSION)

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
    cmd = [
        "run",
        "--rm",
        "odoo",
        "/odoolib/shell.py",
    ]
    if queuejobs:
        cmd += ["--queuejobs"]
    __cmd_interactive(config, *(cmd + [command]))
