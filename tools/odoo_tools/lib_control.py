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
        from .lib_control_with_docker import dev as lib_dev
    return lib_dev(ctx, config, nobuild, kill)


@docker.command(name='ps')
@pass_config
def ps(config):
    if config.use_docker:
        from .lib_control_with_docker import ps as lib_ps
    return lib_ps()

@docker.command(name='exec')
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
def execute(config, machine, args):
    if config.use_docker:
        from .lib_control_with_docker import execute as lib_execute
    lib_execute(machine, args)

@docker.command(name='kill')
@click.argument('machines', nargs=-1)
@click.option('-b', '--brutal', is_flag=True, help='dont wait')
@pass_config
@click.pass_context
def do_kill(ctx, config, machines, brutal=False):
    if config.use_docker:
        from .lib_control_with_docker import do_kill as lib_do_kill
    lib_do_kill(ctx, config, machines, brutal=False)

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
        from .lib_control_with_docker import wait_for_container_postgres as lib_wait_for_container_postgres
    lib_wait_for_container_postgres(config)

@docker.command()
@pass_config
def wait_for_port(config, host, port):
    if config.use_docker:
        from .lib_control_with_docker import wait_for_port as lib_wait_for_port
    lib_wait_for_port(host, port)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def recreate(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import recreate as lib_recreate
    lib_recreate(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-d', '--daemon', is_flag=True)
@pass_config
@click.pass_context
def up(ctx, config, machines, daemon):
    if config.use_docker:
        from .lib_control_with_docker import up as lib_up
    lib_up(ctx, config, machines, daemon, remove_orphans=True)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-v', '--volumes', is_flag=True)
@pass_config
@click.pass_context
def down(ctx, config, machines, volumes):
    if config.use_docker:
        from .lib_control_with_docker import down as lib_down
    lib_down(ctx, config, machines, volumes)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def stop(ctx, config,  machines):
    if config.use_docker:
        from .lib_control_with_docker import stop as lib_stop
    lib_stop(ctx, config,  machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rebuild(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import rebuild as lib_rebuild
    lib_rebuild(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def restart(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import restart as lib_restart
    lib_restart(ctx, config, machines)

@docker.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def rm(ctx, config, machines):
    if config.use_docker:
        from .lib_control_with_docker import rm as lib_rm
    lib_rm(ctx, config, machines)

@docker.command()
@click.argument('machine', required=True)
@pass_config
@click.pass_context
def attach(ctx, config, machine):
    if config.use_docker:
        from .lib_control_with_docker import attach as lib_attach
    lib_attach(ctx, config, machine)

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('--no-cache', is_flag=True)
@click.option('--pull', is_flag=True)
@click.option('--push', is_flag=True)
@pass_config
@click.pass_context
def build(ctx, config, machines, pull, no_cache, push):
    if config.use_docker:
        from .lib_control_with_docker import build as lib_build
    lib_build(ctx, config, machines, pull, no_cache, push)

@docker.command()
@click.argument('machine', required=True)
@click.option('-p', '--ports', is_flag=True, help='With Port 33284')
@pass_config
@click.pass_context
def debug(ctx, config, machine, ports):
    if config.use_docker:
        from .lib_control_with_docker import debug as lib_debug
    lib_debug(ctx, config, machine, ports)

@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def run(ctx, config, volume, machine, args, **kwparams):
    if config.use_docker:
        from .lib_control_with_docker import run as lib_run
    lib_run(ctx, config, volume, machine, args, **kwparams)

@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def runbash(ctx, config, machine, args, **kwparams):
    if config.use_docker:
        from .lib_control_with_docker import runbash as lib_runbash
    lib_runbash(ctx, config, machine, args, **kwparams)

@cli.command(name='logs')
@click.argument('machines', nargs=-1)
@click.option('-n', '--lines', required=False, type=int, default=200)
@click.option('-f', '--follow', is_flag=True)
@pass_config
def logall(config, machines, follow, lines):
    if config.use_docker:
        from .lib_control_with_docker import logall as lib_logall
    lib_logall(machines, follow, lines)

@docker.command()
@click.argument('command', nargs=-1)
@pass_config
def shell(config, command):
    command = "\n".join(command)
    if config.use_docker:
        from .lib_control_with_docker import shell as lib_shell
    lib_shell(command)


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
Commands.register(shell, 'odoo-shell')
