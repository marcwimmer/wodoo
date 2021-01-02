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
from .tools import _start_postgres_and_wait
from .tools import __replace_in_file
from .tools import _wait_for_port
from .tools import __dcexec
from .tools import _get_machines
from .tools import __dc
from .tools import _get_host_ip
from .tools import __needs_docker
import subprocess
from . import Commands

def dev(ctx, config, build, kill):
    """
    starts developing in the odoo container
    """
    from .myconfigparser import MyConfigParser
    myconfig = MyConfigParser(config.files['settings'])
    if not config.devmode:
        click.echo("Requires dev mode.")
        sys.exit(-1)
    if build:
        build(ctx, config)
    if kill:
        click.echo("Killing all docker containers")
        do_kill(ctx, config, machines=[], brutal=True)
        rm(ctx, config, machines=[])
    __dc(['up', '-d'])
    Commands.invoke(ctx, 'kill', machines=["odoo"])
    ip = _get_host_ip()
    proxy_port = myconfig['PROXY_PORT']
    roundcube_port = myconfig['ROUNDCUBE_PORT']
    click.secho("Proxy Port: http://{}:{}".format(ip, proxy_port), fg='green', bold=True)
    click.secho("Mailclient : http://{}:{}".format(ip, roundcube_port), fg='green', bold=True)

    # execute script
    ScriptFile = config.files['start-dev']
    if not ScriptFile.exists():
        click.secho(f"Info: you may provide a startup script here: {ScriptFile}", fg='yellow')
    else:
        FNULL = open(os.devnull, 'w')
        subprocess.Popen([ScriptFile], shell=True, stdout=FNULL)

    Commands.invoke(ctx, 'debug', machine="odoo")

def ps():
    args = ['ps', '-a']
    __dc(args)

def execute(machine, args):
    args = [machine] + list(args)
    __dcexec(args)

def do_kill(ctx, config, machines=[], brutal=False):
    """
    kills running machine
    safely shutdowns postgres and redis

    if not brutal it means softly
    """
    SAFE_KILL = []

    for machine in config.safe_kill.split(","):
        if getattr(config, 'run_{}'.format(machine)):
            SAFE_KILL.append(machine)

    machines = list(machines)
    if not brutal and not config.devmode:
        safe_stop = []
        for machine in SAFE_KILL:
            if not machines or machine in machines:
                if _is_container_running(machine):
                    safe_stop += [machine]

        if safe_stop:
            __dc(["stop", "-t 20"] + safe_stop)  # persist data
    if config.devmode:
        __dc(['kill'] + list(machines))
    else:
        __dc(['stop', '-t 2'] + list(machines))

def force_kill(ctx, config, machine):
    do_kill(ctx, config, machine=machine, brutal=True)

def wait_for_container_postgres(config):
    if config.USE_DOCKER:
        _start_postgres_and_wait(config)

def wait_for_port(host, port):
    port = int(port)
    _wait_for_port(host=host, port=port)


def recreate(ctx, config, machines=[]):
    machines = list(machines)
    __dc(['up', '--no-start', '--force-recreate'] + machines)

def up(ctx, config, machines=[], daemon=False, remove_orphans=True):
    machines = list(machines)

    options = [
        # '--remove-orphans', # lost data with that; postgres volume suddenly new after rm?
    ]
    if daemon:
        options += ['-d']
    if remove_orphans:
        options += ['--remove-orphans']
    __dc(['up'] + options + machines)

def down(ctx, config, machines=[], volumes=False):
    machines = list(machines)

    options = []
    # '--remove-orphans', # lost data with that; postgres volume suddenly new after rm?
    if volumes:
        options += ['--volumes']
    __dc(['down'] + options + machines)

def stop(ctx, config,  machines=[]):
    do_kill(ctx, config, machines=machines)

def rebuild(ctx, config, machines=[]):
    Commands.invoke(ctx, 'compose', customs=config.customs)
    build(ctx, config, machines=machines, no_cache=True)

def restart(ctx, config, machines=[]):
    machines = list(machines)

    do_kill(ctx, config, machines=machines)
    up(ctx, config, machines=machines, daemon=True)

def rm(ctx, config, machines=[]):
    __needs_docker(config)
    machines = list(machines)
    __dc(['rm', '-f'] + machines)

def attach(ctx, config, machine):
    """
    attaches to running machine
    """
    __needs_docker(config)
    _display_machine_tips(config, machine)
    bash = _get_bash_for_machine(machine)
    __cmd_interactive('exec', machine, bash)

def build(ctx, config, machines=[], pull=False, no_cache=False, push=False):
    """
    no parameter all machines, first parameter machine name and passes other params; e.g. ./odoo build asterisk --no-cache"
    """
    options = []
    if pull:
        options += ['--pull']
    if no_cache:
        options += ['--no-cache']
        if '--pull' not in options:
            options += ['--pull']

    __dc(['build'] + options + list(machines), env={
        'ODOO_VERSION': config.odoo_version,  # at you developer: do not mismatch with build args
    })

def debug(ctx, config, machine, ports):
    """
    starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
    """
    # puts endless loop into container command and then attaches to it;
    # by this, name resolution to the container still works
    if not config.devmode:
        _askcontinue(config, "Current machine {} is dropped and restartet with service ports in bash. Usually you have to type /debug.sh then.".format(machine))
    # shutdown current machine and start via run and port-mappings the replacement machine
    do_kill(ctx, config, machines=[machine])
    rm(ctx, config, machines=[machine])
    src_files = [config.files['debugging_template_onlyloop']]
    if ports:
        src_files += [config.files['debugging_template_withports']]

    cmd_prefix = []
    for i, filepath in enumerate(src_files):
        dest = config.files['debugging_composer']
        dest = dest.parent / dest.name.replace(".yml", ".{}.yml".format(i))
        shutil.copy(filepath, dest)
        __replace_in_file(dest, "${CUSTOMS}", config.customs)
        __replace_in_file(dest, "${NAME}", machine)
        __replace_in_file(dest, "${DOCKER_COMPOSE_VERSION}", config.YAML_VERSION)

        # TODO make configurable in machines
        PORT = str({
            'odoo': 8069,
            'odoo_debug': 8069
        }.get(machine, 80))
        __replace_in_file(dest, "{machine_main_port}", PORT)

        cmd_prefix += ['-f', dest]

    __dc(cmd_prefix + ['up', '-d', machine])
    attach(ctx, config, machine=machine)

def run(ctx, config, volume, machine, args, **kwparams):
    """
    extract volume mounts

    """
    if args and args[0] == 'bash' and len(args) == 1:
        runbash(ctx, config, machine=machine)
        return
    __dcrun([machine] + list(args), **kwparams)

def runbash(ctx, config, machine, args, **kwparams):
    _display_machine_tips(config, machine)
    bash = _get_bash_for_machine(machine)
    cmd = ['run', machine]
    if args:
        cmd += args
    else:
        cmd += [bash]
    __cmd_interactive(*tuple(cmd))


def logall(machines, follow, lines):
    cmd = ['logs']
    if follow:
        cmd += ['-f']
    if lines:
        cmd += ['--tail={}'.format(lines)]
    cmd += list(machines)
    __dc(cmd)


def shell(command=""):
    __cmd_interactive(
        'run',
        'odoo',
        '/usr/bin/python3',
        '/odoolib/shell.py',
        command,
    )
