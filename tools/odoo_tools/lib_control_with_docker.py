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
from .tools import _sanity_check
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
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from . import odoo_user_conf_dir
import subprocess

@cli.group(cls=AliasedGroup)
@pass_config
def docker(config):
    pass

@docker.command()
@click.option("-B", "--nobuild", is_flag=True)
@click.option("-k", "--kill", is_flag=True)
@pass_config
@click.pass_context
def dev(ctx, config, nobuild, kill):
    """
    starts developing in the odoo container
    """
    from . import MyConfigParser
    myconfig = MyConfigParser(files['settings'])
    if not config.devmode:
        click.echo("Requires dev mode.")
        sys.exit(-1)
    ctx.invoke(do_kill, brutal=True)
    ctx.invoke(rm)
    if not nobuild:
        ctx.invoke(build)
    if kill:
        click.echo("Killing all docker containers")
        os.system("docker kill $(docker ps -q)")
    __dc(['up', '-d'])
    Commands.invoke(ctx, 'kill', machines=["odoo"])
    ip = _get_host_ip()
    proxy_port = myconfig['PROXY_PORT']
    roundcube_port = myconfig['ROUNDCUBE_PORT']
    click.secho("Proxy Port: http://{}:{}".format(ip, proxy_port), fg='green', bold=True)
    click.secho("Mailclient : http://{}:{}".format(ip, roundcube_port), fg='green', bold=True)

    # execute script
    ScriptFile = odoo_user_conf_dir / 'start-dev'
    if not ScriptFile.exists():
        click.secho("Info: Not found: {} - not executing anything on startup".format(ScriptFile))
    FNULL = open(os.devnull, 'w')
    subprocess.Popen([ScriptFile], shell=True, stdout=FNULL)

    Commands.invoke(ctx, 'debug', machine="odoo")

@docker.command(name='exec')
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
def execute(machine, args):
    args = [machine] + list(args)
    __dcexec(args)

@docker.command(name='kill')
@click.argument('machines', nargs=-1)
@click.option('-b', '--brutal', is_flag=True, help='dont wait')
@pass_config
@click.pass_context
def do_kill(ctx, config, machines, brutal=False):
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
    if config.run_postgres_in_ram and not machines:
        machines = list(filter(lambda x: x != 'postgres', _get_machines()))
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

@docker.command()
@click.pass_context
def force_kill(ctx, machine):
    ctx.invoke(do_kill, machine=machine, brutal=True)

@docker.command()
@pass_config
def wait_for_container_postgres(config):
    if config.USE_DOCKER:
        _start_postgres_and_wait(config)

@docker.command()
def wait_for_port(host, port):
    port = int(port)
    _wait_for_port(host=host, port=port)


@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def recreate(ctx, config, machines):
    machines = list(machines)
    if not machines and 'postgres' not in machines:
        if config.run_postgres_in_ram:
            machines = list(filter(lambda x: x != 'postgres', _get_machines()))

    __dc(['up', '--no-start', '--force-recreate'] + machines)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-d', '--daemon', is_flag=True)
@pass_config
@click.pass_context
def up(ctx, config, machines, daemon):
    _sanity_check(config)
    machines = list(machines)

    if not machines and 'postgres' not in machines:
        if config.run_postgres_in_ram:
            machines = list(filter(lambda x: x != 'postgres', _get_machines()))

    options = [
    ]
    if daemon:
        options += ['-d']
    __dc(['up'] + options + machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def stop(ctx, config,  machines):
    ctx.invoke(do_kill, machines=machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rebuild(ctx, config, machines):
    Commands.invoke(ctx, 'compose', customs=config.customs)
    ctx.invoke(build, machines=machines, no_cache=True)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def restart(ctx, config, machines):
    machines = list(machines)
    if not machines and 'postgres' not in machines:
        if config.run_postgres_in_ram:
            machines = list(filter(lambda x: x != 'postgres', _get_machines()))

    ctx.invoke(do_kill, machines=machines)
    ctx.invoke(up, machines=machines, daemon=True)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rm(ctx, config, machines):
    __needs_docker(config)
    machines = list(machines)
    if not machines and 'postgres' not in machines:
        if config.run_postgres_in_ram:
            machines = list(filter(lambda x: x != 'postgres', _get_machines()))
    __dc(['rm', '-f'] + machines)

@docker.command()
@click.argument('machine', required=True)
@pass_config
def attach(config, machine):
    """
    attaches to running machine
    """
    __needs_docker(config)
    _display_machine_tips(machine)
    bash = _get_bash_for_machine(machine)
    __cmd_interactive('exec', machine, bash)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('--no-cache', is_flag=True)
@click.option('--pull', is_flag=True)
@click.option('--push', is_flag=True)
@pass_config
def build(config, machines, pull, no_cache, push):
    """
    no parameter all machines, first parameter machine name and passes other params; e.g. ./odoo build asterisk --no-cache"
    """
    options = []
    if pull:
        options += ['--pull']
    if no_cache:
        options += ['--no-cache']

    __dc(['build'] + options + list(machines), env={
        'ODOO_VERSION': config.odoo_version
    })

@docker.command()
@click.argument('machine', required=True)
@click.option('-p', '--ports', is_flag=True, help='With Port 33824')
@pass_config
@click.pass_context
def debug(ctx, config, machine, ports):
    """
    starts /bin/bash for just that machine and connects to it; if machine is down, it is powered up; if it is up, it is restarted; as command an endless bash loop is set"
    """
    from . import commands

    # puts endless loop into container command and then attaches to it;
    # by this, name resolution to the container still works
    if not config.devmode:
        _askcontinue(config, "Current machine {} is dropped and restartet with service ports in bash. Usually you have to type /debug.sh then.".format(machine))
    # shutdown current machine and start via run and port-mappings the replacement machine
    ctx.invoke(do_kill, machines=[machine])
    ctx.invoke(rm, machines=[machine])
    src_files = [files['debugging_template_onlyloop']]
    if ports:
        src_files += [files['debugging_template_withports']]

    for i, filepath in enumerate(src_files):
        dest = files['debugging_composer']
        dest = dest.parent / dest.name.replace(".yml", ".{}.yml".format(i))
        shutil.copy(filepath, dest)
        __replace_in_file(dest, "${CUSTOMS}", config.customs)
        __replace_in_file(dest, "${NAME}", machine)

        # TODO make configurable in machines
        PORT = str({
            'odoo': 8069,
            'odoo_debug': 8069
        }.get(machine, 80))
        __replace_in_file(dest, "{machine_main_port}", PORT)

        commands['dc'] += ['-f', dest]

    __dc(['up', '-d', machine])
    ctx.invoke(attach, machine=machine)


@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def run(ctx, config, volume, machine, args, **kwparams):
    """
    extract volume mounts

    """
    if args and args[0] == 'bash' and len(args) == 1:
        ctx.invoke(runbash, machine=machine)
        return
    __dcrun([machine] + list(args), **kwparams)

@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def runbash(ctx, config, machine, args, **kwparams):
    _display_machine_tips(machine)
    bash = _get_bash_for_machine(machine)
    cmd = ['run', machine]
    if args:
        cmd += args
    else:
        cmd += [bash]
    __cmd_interactive(*tuple(cmd))

@cli.command(name='bash')
def simplebash(*parameters):
    if not parameters:
        print("Call commands by just typing odoo<enter>")
        os.system("bash --noprofile")
    else:
        os.system("bash --noprofile -c {}".format(" ".join(parameters)))

@cli.command(name='logs')
@click.argument('machines', nargs=-1)
@click.option('-t', '--tail', required=False, type=int, default=200)
@click.option('-f', '--follow', is_flag=True)
def logall(machines, follow, tail):
    cmd = ['logs']
    if follow:
        cmd += ['-f']
    if tail:
        cmd += ['--tail={}'.format(tail)]
    cmd += list(machines)
    __dc(cmd)

@docker.command()
def springclean():
    os.system("docker system prune")
    click.echo("removing dead containers")
    os.system('docker ps -a -q | while read -r id; do docker rm "$id"; done')

    click.echo("Remove untagged images")
    os.system('docker images | grep "<none>" | awk \'{ click.echo "docker rmi " $3 }\' | bash')

    click.echo("delete unwanted volumes (can pass -dry-run)")
    os.system('docker images -q -f="dangling=true" | while read -r id; do docker rmi "$id"; done')


Commands.register(run)
Commands.register(runbash)
Commands.register(do_kill, 'kill')
Commands.register(up)
Commands.register(wait_for_container_postgres)
Commands.register(build)
Commands.register(rm)
Commands.register(recreate)
Commands.register(debug)
Commands.register(restart)
