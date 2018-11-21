import subprocess
import sys
import shutil
import hashlib
import os
import tempfile
import click
from tools import __assert_file_exists
from tools import __system
from tools import __safe_filename
from tools import __cmd_interactive
from tools import __find_files
from tools import __read_file
from tools import __write_file
from tools import __append_line
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from tools import _fix_permissions
from tools import _remove_temp_directories
from tools import _prepare_filesystem
from . import cli, pass_config, dirs, files, Commands
from lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def admin(config):
    pass


@admin.command()
def fix_permissions():
    _fix_permissions()

@admin.command()
@pass_config
def status(config):
    color = 'yellow'
    click.echo("customs: ", nl=False)
    click.echo(click.style(config.customs, color, bold=True))
    click.echo("version: ", nl=False)
    click.echo(click.style(config.odoo_version, color, bold=True))
    click.echo("db: ", nl=False)
    click.echo(click.style(config.dbname, color, bold=True))
    if config.run_postgres:
        print("dockerized postgres")
        if config.run_postgres_in_ram:
            print("postgres is in-ram")
    else:
        print("postgres: {}:{}/{}".format(
            config.db_host,
            config.db_port,
            config.dbname,
        ))

@admin.command()
def springclean():
    os.system("docker system prune")
    click.echo("removing dead containers")
    os.system('docker ps -a -q | while read -r id; do docker rm "$id"; done')

    click.echo("Remove untagged images")
    os.system('docker images | grep "<none>" | awk \'{ click.echo "docker rmi " $3 }\' | bash')

    click.echo("delete unwanted volumes (can pass -dry-run)")
    os.system('docker images -q -f="dangling=true" | while read -r id; do docker rmi "$id"; done')

@admin.command()
@pass_config
def pack(config):
    from . import odoo_config
    url = "ssh://git@git.clear-consulting.de:50004/odoo-deployments/{}".format(config.customs)
    folder = os.path.join(os.environ['LOCAL_ODOO_HOME'], 'data/src/deployments', config.customs)
    if not os.path.isdir(os.path.dirname(folder)):
        os.makedirs(os.path.dirname(folder))

    if not os.path.exists(folder):
        __system([
            "git",
            "clone",
            url,
            os.path.basename(folder),
        ], cwd=os.path.dirname(folder), suppress_out=False)

    __system([
        "rsync",
        odoo_config.customs_dir() + "/",
        folder + "/",
        '-ar',
        '--exclude=.git',
        '--exclude=.pyc',
        '--delete-after',
    ], cwd=odoo_config.customs_dir(), suppress_out=False)

    if os.path.islink(os.path.join(odoo_config.customs_dir(), 'common')):
        os.unlink(os.path.join(folder, 'common'))
        __system([
            "rsync",
            odoo_config.customs_dir() + "/common/",
            folder + "/common/",
            '-arL',
            '--exclude=.git',
            '--exclude=.pyc',
            '--delete-after',
        ], cwd=odoo_config.customs_dir(), suppress_out=False)

    # remove .gitignore - could contain odoo for example
    gitignore = os.path.join(folder, '.gitignore')
    with open(gitignore, 'w') as f:
        f.write("""
*.pyc
""")

    subprocess.Popen(["find", "-name", "*.pyc", "-delete"], cwd=folder).wait()

    # sync modules

    # TODO filter out not licensed modules
    for linkdir in [
        'common',
    ]:
        if os.path.islink(linkdir):
            os.unlink(os.path.join(folder, linkdir))
            __system([
                "rsync",
                os.path.join(odoo_config.customs_dir(), "../../modules", config.odoo_version) + "/",
                folder + "/{}/".format(linkdir),
                '-ar',
                '--exclude=.git',
            ], cwd=odoo_config.customs_dir(), suppress_out=False)

    __system(["git", "add", "."], cwd=folder, suppress_out=False)
    __system(["git", "commit", "-am 'new deployment'"], cwd=folder, suppress_out=False)
    __system(["git", "push"], cwd=folder, suppress_out=False)

@admin.command(name='set-setting')
@click.argument('key', required=True)
@click.argument('value', required=True)
def set_setting(key, value):
    from . import MyConfigParser
    config = MyConfigParser(files['settings'])
    config[key.upper()] = value
    config.write()

@admin.command()
def shell():
    __cmd_interactive('run', 'odoo', '/bin/bash', '/shell.sh')


Commands.register(status)
Commands.register(fix_permissions)
Commands.register(set_setting)
