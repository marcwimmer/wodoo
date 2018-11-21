import shutil
import hashlib
import os
import tempfile
import click
from tools import __assert_file_exists
from tools import __system
from tools import __safe_filename
from tools import __find_files
from tools import __read_file
from tools import __write_file
from tools import __append_line
from tools import __replace_in_file
from tools import _sanity_check
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from . import cli, pass_config, dirs, files
from lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def setup(config):
    pass

@setup.command()
@pass_config
def sanity_check(config):
    _sanity_check(config)

@setup.command(name='startup')
@pass_config
def setup_startup(config):
    """
    Installs systemd scripts.
    """
    if os.path.exists("/sbin_host/initctl"):
        raise Exception("Not impl")
    else:
        click.echo("Setting up systemd script for startup")
        servicename = os.path.expandvars("${CUSTOMS}_odoo.service")
        file = os.path.join("/tmp_host, servicename")

        # echo "Setting up upstart script in $file"
        shutil.copy(os.path.join(dirs['odoo_home'], 'config', 'systemd'), file)
        __replace_in_file(file, "${CUSTOMS}", config.customs)
        __replace_in_file(file, "${PATH}", config.HOST_ODOO_HOME)

        click.echo("Please execute on host now (perhaps as sudo):")
        click.echo("""cp /tmp/{servicename} /etc/systemd/system")
        systemctl stop {servicename}
        systemctl disable {servicename}
        systemctl daemon-reload
        systemctl reset-failed
        systemctl enable {servicename}
        systemctl start {servicename}
        """.format(servicename=servicename)
                   )
