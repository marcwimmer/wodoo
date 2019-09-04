import requests
from pathlib import Path
import subprocess
import sys
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __dc
from .tools import _askcontinue
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __cmd_interactive
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import _fix_permissions
from .tools import _prepare_filesystem
from .tools import remove_webassets
from .odoo_config import get_odoo_addons_paths
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def admin(config):
    pass


@admin.command()
@pass_config
def fix_permissions(config):
    _fix_permissions(config)

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
    cmd = ['config', '--services']
    __dc(cmd)
    cmd = ['config', '--volumes']
    __dc(cmd)

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
    from .odoo_config import MANIFEST
    manifest = MANIFEST()
    url = manifest.get("deploy-url", "ssh://git@git.clear-consulting.de:50004/odoo-deployments/{}".format(config.customs))
    folder = Path(os.path.expanduser("~/.odoo/pack_for_deploy")) / 'odoo-deployments' / config.customs
    folder.parent.mkdir(parents=True, exist_ok=True)

    if not folder.exists():
        subprocess.check_call([
            "git",
            "clone",
            url,
            folder.name,
        ], cwd=folder.parent)

    subprocess.check_call([
        "git",
        "pull",
    ], cwd=folder)

    # clone to tmp directory and cleanup - remove unstaged and so on
    tmp_folder = Path('/tmp/pack')
    subprocess.check_call([
        "rsync",
        str(odoo_config.customs_dir()) + "/",
        str(tmp_folder) + "/",
        '-ar',
        '--exclude=.pyc',
        '--delete-after',
    ], cwd=odoo_config.customs_dir())
    subprocess.check_call([
        "git",
        "clean",
        "-xdff",
    ], cwd=tmp_folder)
    subprocess.check_call([
        "git",
        "submodule",
        "foreach",
        "git",
        "clean",
        "-xdff",
    ], cwd=tmp_folder)

    # remove set_traces and other
    # remove ignore file to make ag find everything
    ignore_file = tmp_folder / '.ignore'
    if ignore_file.exists():
        ignore_file.unlink()
    output = subprocess.check_output(["ag", "-l", "set_trace", "-G", ".py"], cwd=tmp_folder).decode('utf-8')
    for file in output.split("\n"):
        file = tmp_folder / file
        if file.is_dir():
            continue
        if file.name.startswith("."):
            continue
        print(file)
        content = file.read_text()
        if 'set_trace' in content:
            content = content.replace("import pudb; set_trace()", "pass")
            content = content.replace("import pudb;set_trace()", "pass")
            content = content.replace("set_trace()", "pass")
            file.write_text(content)
    ast_file = tmp_folder / '.odoo.ast'
    if ast_file.exists():
        ast_file.unlink()

    subprocess.check_call([
        "rsync",
        str(tmp_folder) + "/",
        str(folder) + "/",
        '-ar',
        '--exclude=.git',
        '--exclude=.pyc',
        '--delete-after',
    ], cwd=odoo_config.customs_dir())

    # remove .gitignore - could contain odoo for example
    gitignore = folder / '.gitignore'
    with gitignore.open('w') as f:
        f.write("""
*.pyc
""")

    subprocess.call(["find", '.', "-name", "*.pyc", "-delete"], cwd=folder)

    subprocess.call(["git", "add", "."], cwd=folder)
    subprocess.call(["git", "commit", "-am 'new deployment'"], cwd=folder)
    subprocess.call(["git", "push"], cwd=folder)

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
    __cmd_interactive('run', 'odoo', '/usr/bin/python3', '/odoolib/shell.py')


@admin.command(name="remove-web-assets")
@pass_config
@click.pass_context
def remove_web_assets(ctx, config):
    """
    if odoo-web interface is broken (css, js) then purging the web-assets helps;
    they are usually recreated when admin login
    """
    from module_tools.odoo_config import current_version
    _askcontinue(config)
    conn = config.get_odoo_conn().clone(dbname=config.dbname)
    remove_webassets(conn)
    if current_version() <= 10.0:
        click.echo("Please login as admin, so that assets are recreated.")

@admin.command()
@pass_config
@click.pass_context
def show_effective_settings(ctx, config):
    from . import MyConfigParser
    config = MyConfigParser(files['settings'])
    for k in sorted(config.keys()):
        click.echo("{}={}".format(
            k,
            config[k]
        ))

@admin.command(help="Syncs all files from source to docker volume source")
@pass_config
@click.pass_context
def fullsync(ctx, config):
    r = requests.get(config.fssync_service_url + "/fullsync")
    r.raise_for_status()


Commands.register(status)
Commands.register(fix_permissions)
Commands.register(set_setting)
Commands.register(pack)
