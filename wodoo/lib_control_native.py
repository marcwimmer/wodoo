import os
import tempfile
import click
from pathlib import Path
from .odoo_config import current_version
from .odoo_config import customs_dir
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
import subprocess

@cli.group(cls=AliasedGroup)
@pass_config
def control(config):
    pass

@control.command()
@pass_config
@click.pass_context
def dev(ctx, config):
    """
    starts developing in the odoo container
    """
    from .myconfigparser import MyConfigParser
    myconfig = MyConfigParser(config.files['settings'])
    proxy_port = myconfig['PROXY_PORT']
    roundcube_port = myconfig['ROUNDCUBE_PORT']
    ip = '127.0.0.1'
    click.secho("Proxy Port: http://{}:{}".format(ip, proxy_port), fg='green', bold=True)
    click.secho("Mailclient : http://{}:{}".format(ip, roundcube_port), fg='green', bold=True)
    _exec_in_virtualenv(config, ['python', _path_odoolib() / 'debug.py'])


def _update_command(config, params):
    _exec_in_virtualenv(config, ['python', _path_odoolib() / 'update_modules.py'] + params)


def up(ctx, config, machines=[], daemon=False, remove_orphans=True):
    _exec_in_virtualenv(config, ['python', _path_odoolib() / 'run.py'])


@control.command()
def shell(config):
    subprocess.call([
        'python',
        ''
    ])
    _exec_in_virtualenv(config, ['python', _path_odoolib() / 'shell.py'])

def _path_odoolib():
    return Path(os.environ['ODOO_HOME']) / 'images' / 'odoo' / 'bin'

def _exec_in_virtualenv(config, cmd):
    filename = Path(tempfile.mktemp(suffix='.sh'))
    from .myconfigparser import MyConfigParser
    myconfig = MyConfigParser(config.files['settings'])

    def _quoted(x):
        return "'{}'".format(x)
    content = []
    for key in myconfig.keys():
        content.append("export {}='{}'".format(key, myconfig.get(key)))
    files = config.files
    dirs = config.dirs

    raise Exception('adapt after pip compatible')

    filename.write_text('\n'.join(content + list((
        f'set -ex',
        f'export DEBUGGER_WATCH="{files["run/odoo_debug.txt"]}"',
        f'export ODOO_CONFIG_TEMPLATE_DIR="{dirs["images"] / "odoo" / "config" / str(current_version()) / "config"}"',
        f'export ODOO_CONFIG_DIR="{dirs["run_native_config_dir"]}"',
        f'export ODOOLIB="{dirs["images"] / "odoo" / "bin"}"',
        f'export ODOO_USER="$(whoami)"',
        f'export ODOO_DATA_DIR="{dirs["odoo_data_dir"]}"',
        f'export SERVER_DIR="{customs_dir()}/odoo"',
        f'export PYTHONPATH="{dirs["."]}"',
        f'export RUN_DIR="{dirs["run"]}"',
        f'export NO_SOFFICE=1',
        f'export OUT_DIR="{dirs["run_native_out_dir"]}"',
        f'export INTERNAL_ODOO_PORT=8069',
        f"source '{dirs['venv']}/bin/activate'",
        f"which python",
        f"python --version",
        f"{' '.join(map(_quoted, cmd))}",
    ))))

    subprocess.call(["/bin/bash", filename])
    print("--------------------------------------")
    # print(filename.read_text())
    # filename.unlink()
