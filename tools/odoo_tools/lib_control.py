import click
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup

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
    if config.use_docker:
        from .lib_control_with_docker import dev# NOQA
    return dev(ctx, config, nobuild, kill)


@docker.command(name='ps')
@pass_config
def ps(config):
    if config.use_docker:
        from .lib_control_with_docker import ps
    return ps()

@docker.command(name='exec')
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
def execute(config, machine, args):
    if config.use_docker:
        from .lib_control_with_docker import execute
    execute(machine, args)

@docker.command(name='kill')
@click.argument('machines', nargs=-1)
@click.option('-b', '--brutal', is_flag=True, help='dont wait')
@pass_config
@click.pass_context
def do_kill(ctx, config, machines, brutal=False):
    if config.use_docker:
        from .lib_control_with_docker import do_kill
    do_kill(ctx, config, machines, brutal=False)

@docker.command()
@pass_config
@click.pass_context
def force_kill(ctx, config, machine):
    if config.use_docker:
        from .lib_control_with_docker import force_kill
    force_kill(ctx, machine)

@docker.command()
@pass_config
def wait_for_container_postgres(config):
    if config.use_docker:
        from .lib_control_with_docker import wait_for_container_postgres
    wait_for_container_postgres(config)

@docker.command()
@pass_config
def wait_for_port(config, host, port):
    if config.use_docker:
        from .lib_control_with_docker import wait_for_port
    wait_for_port(host, port)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def recreate(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import recreate
    recreate(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-d', '--daemon', is_flag=True)
@pass_config
@click.pass_context
def up(ctx, config, machines, daemon):
    if config.use_docker:
        from .lib_control_with_docker import up
    up(ctx, config, machines, daemon)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-v', '--volumes', is_flag=True)
@pass_config
@click.pass_context
def down(ctx, config, machines, volumes):
    if config.use_docker:
        from .lib_control_with_docker import down
    down(ctx, config, machines, volumes)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def stop(ctx, config,  machines):
    if config.use_docker:
        from .lib_control_with_docker import stop
    stop(ctx, config,  machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rebuild(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import rebuild
    rebuild(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def restart(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import restart
    restart(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rm(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import rm
    rm(ctx, config, machines)

@docker.command()
@click.argument('machine', required=True)
@pass_config
def attach(config, machine):
    if config.use_docker:
        from .lib_control_with_docker import attach
    attach(config, machine)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('--no-cache', is_flag=True)
@click.option('--pull', is_flag=True)
@click.option('--push', is_flag=True)
@pass_config
def build(config, machines, pull, no_cache, push):
    if config.use_docker:
        from .lib_control_with_docker import build
    build(config, machines, pull, no_cache, push)

@docker.command()
@click.argument('machine', required=True)
@click.option('-p', '--ports', is_flag=True, help='With Port 33824')
@pass_config
@click.pass_context
def debug(ctx, config, machine, ports):
    if config.use_docker:
        from .lib_control_with_docker import debug
    debug(ctx, config, machine, ports)


@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def run(ctx, config, volume, machine, args, **kwparams):
    if config.use_docker:
        from .lib_control_with_docker import run
    run(ctx, config, volume, machine, args, **kwparams)

@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def runbash(ctx, config, machine, args, **kwparams):
    if config.use_docker:
        from .lib_control_with_docker import runbash
    runbash(ctx, config, machine, args, **kwparams)

@cli.command(name='logs')
@click.argument('machines', nargs=-1)
@click.option('-n', '--lines', required=False, type=int, default=200)
@click.option('-f', '--follow', is_flag=True)
@pass_config
def logall(config, machines, follow, lines):
    if config.use_docker:
        from .lib_control_with_docker import logall
    logall(machines, follow, lines)

@docker.command()
@pass_config
def shell(config):
    if config.use_docker:
        from .lib_control_with_docker import shell
    shell()


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
