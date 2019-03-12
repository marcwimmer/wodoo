import time
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __find_files
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from .tools import __set_db_ownership
from .tools import __dc
from .tools import __dcrun
from .tools import _display_machine_tips
from .tools import _get_bash_for_machine
from .tools import __cmd_interactive
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

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


@cli.command()
@click.argument('machine', required=True)
@click.argument('args', nargs=-1)
@pass_config
@click.pass_context
def run(ctx, config, volume, machine, args, **kwparams):
    """
    extract volume mounts

    """
    __set_db_ownership(config)
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
    __set_db_ownership(config)
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


Commands.register(run)
Commands.register(runbash)
