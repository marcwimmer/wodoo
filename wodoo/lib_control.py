import click
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import execute_script
import subprocess
import json
from .tools import download_file_and_move
from pathlib import Path

@cli.group(cls=AliasedGroup)
@pass_config
def docker(config):
    pass

@docker.command()
@click.option("-b", "--build", is_flag=True)
@click.option("-k", "--kill", is_flag=True)
@pass_config
@click.pass_context
def dev(ctx, config, build, kill):
    if config.use_docker:
        from .lib_control_with_docker import dev as lib_dev
    return lib_dev(ctx, config, build, kill)


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
    else:
        from .lib_control_native import up as lib_up
    lib_up(ctx, config, machines, daemon, remove_orphans=True)
    execute_script(config, config.files['after_up_script'], 'Possible after up script here:')

@docker.command()
@click.argument('machines', nargs=-1)
@click.option('-v', '--volumes', is_flag=True)
@click.option('--remove-orphans', is_flag=True)
@pass_config
@click.pass_context
def down(ctx, config, machines, volumes, remove_orphans):
    if config.use_docker:
        from .lib_control_with_docker import down as lib_down
    lib_down(ctx, config, machines, volumes, remove_orphans)

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
@click.option('-c', '--command', required=False, help="Like /odoolib/debug.py")
@click.option('-p', '--ports', is_flag=True, help='With Port 33284')
@pass_config
@click.pass_context
def debug(ctx, config, machine, ports, command):
    if config.use_docker:
        from .lib_control_with_docker import debug as lib_debug
    lib_debug(ctx, config, machine, ports, cmd=command)

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

@docker.command()
@click.option('-f', '--filter')
@pass_config
def show_volumes(config, filter):
    import yaml
    from tabulate import tabulate
    from .lib_control_with_docker import _get_volume_size
    volumes = subprocess.check_output(["docker", "volume", "ls"]).decode('utf-8').split("\n")[1:]
    volumes = [x.split(" ")[-1] for x in volumes]
    volumes = [[x] for x in volumes if '_' in x]  # named volumes
    volumes = [x for x in volumes if config.project_name in x[0]]
    if filter:
        volumes = [x for x in volumes if filter in x]
    for volume in volumes:
        size = _get_volume_size(volume[0])
        volume.append(size)
    click.echo(tabulate(volumes, ["Volume", "Size"]))

    click.secho("\ndocker-compose file:", bold=True)
    compose = yaml.safe_load(config.files['docker_compose'].read_text())
    for volume in compose['volumes']:
        click.secho(f"docker-compose volume: {volume}")

@docker.command()
@click.option('-a', '--show-all', is_flag=True)
@click.option('-f', '--filter')
@click.option('-B', '--no-backup', is_flag=True)
@pass_config
@click.pass_context
def transfer_volume_content(context, config, show_all, filter, no_backup):
    import shutil
    import inquirer
    from pathlib import Path
    from .lib_control_with_docker import _get_volume_size
    from .lib_control_with_docker import _get_volume_hostpath
    volumes = subprocess.check_output(["docker", "volume", "ls"]).decode('utf-8').split("\n")[1:]
    volumes = [x.split(" ")[-1] for x in volumes]
    volumes = [x for x in volumes if '_' in x]  # named volumes

    if filter:
        volumes = [x for x in volumes if filter in x]

    def add_size(volume):
        size = _get_volume_size(volume)
        return f"{volume} [{size}]"

    if show_all:
        volumes = list(map(add_size, volumes))
        volumes_filtered_to_project = [x for x in volumes if config.project_name in x]

        volumes1 = volumes
        volumes2 = volumes_filtered_to_project

    else:
        volumes_filtered_to_project = [x for x in volumes if config.project_name in x]
        volumes_filtered_to_project = list(map(add_size, volumes_filtered_to_project))

        volumes1 = volumes_filtered_to_project
        volumes2 = volumes_filtered_to_project

    questions = [
        inquirer.List(
            'volume',
            message="Select source:".format(config.customs, config.dbname),
            choices=volumes1,
        ),
    ]
    answers = inquirer.prompt(questions)
    if not answers or not answers['volume']:
        return

    source = answers['volume']
    volumes2.pop(volumes2.index(source))
    questions = [
        inquirer.List(
            'volume',
            message="Select Destination:".format(config.customs, config.dbname),
            choices=volumes2,
        ),
    ]
    answers = inquirer.prompt(questions)
    if not answers or not answers['volume']:
        return
    source = _get_volume_hostpath(source.split(" [")[0])
    dest = _get_volume_hostpath(answers['volume'].split(" [")[0])

    tasks = []
    tasks.append(f'rsync -ar --delete-after {source.name} to {dest.name}')
    for i, task in enumerate(tasks):
        click.secho(f"{i}. {task}")
    answer = inquirer.prompt([inquirer.Confirm('continue', message=("Continue?"))])
    if not answer['continue']:
        return
    Commands.invoke(context, 'down')

    if not no_backup:
        click.secho("Rsyncing files to /tmp as backup...")
        backup_name = str(Path("/tmp/") / dest.name) + ".bak"
        subprocess.check_call([
            '/usr/bin/sudo',
            'rsync',
            '-ar',
            str(dest / '_data') + '/',
            backup_name + '/',
        ])
        click.secho(f"Made backup in {backup_name}")

    click.secho(f"Rsyncing files from old source to {dest}")

    command = [
        'rsync',
        '-arP',
        '--delete-after',
        str(source / '_data') + '/',
        str(dest / '_data') + '/',
    ]
    subprocess.check_call([
        '/usr/bin/sudo',
    ] + command)


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
Commands.register(down)
