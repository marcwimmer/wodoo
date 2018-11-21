"""

Utilities to access the customer's odoo.

Place in customs:

.access/config
.access/id_rsa

.access/config:
{
        "area": {
                "prod":
                {
                        "user": "cpadmin",
                        "host": "zergling.rox",
                        "odoo_base": "/opt/odoo",
                        "keyfile": "id_rsa"
                }
        }
}

"""
import sys
import os
import json
import click
from tools import __read_file
from lib_clickhelpers import AliasedGroup
from tools import __dcrun, __dc, __remove_postgres_connections, __execute_sql, __dcexec
from tools import get_dockercompose
from . import cli, pass_config, dirs, files, Commands

@cli.group(cls=AliasedGroup)
@pass_config
def sync(config):
    """
    Database related actions.
    """
    click.echo("database-name: {}, in ram: {}".format(config.dbname, config.run_postgres_in_ram))
    pass

def get_config(area):
    conf = __get_area(area)
    conf['keyfile'] = os.path.join(dirs['customs'], '.access', conf['keyfile'])
    return conf

def get_areas():
    return __get_config_file().keys()

def _get_docker_volume_dir():
    return "/var/lib/docker/volumes"

def __get_area(area):
    return __get_config_file()[area]

def __get_config_file():
    p = os.path.join(dirs['customs'], '.access/config')
    content = __read_file(p)
    return eval(content)

def __exec_remote_odoo_get_string(access_config, *params):
    args = [
        '-v',
        access_config['keyfile'] + ":" + '/root/.ssh/id_rsa',
        'volumesyncer',
        '/usr/bin/ssh',
        '-oStrictHostKeyChecking=no',
        '-oLogLevel=quiet',
        '-i', '/root/.ssh/id_rsa',
        'root@' + access_config['host'],
        os.path.join(access_config['odoo_base'], 'odoo'),
    ] + list(params)
    res = __dcrun(args, interactive=True)
    res = res or ''
    res = res.strip()
    return res

@sync.command(name="volumename")
@click.argument('service', required=True)
@click.argument('local_path', required=True)
@click.option('--full', is_flag=True)
def volume_name(service, local_path, full):
    compose = get_dockercompose()
    compose['services'][service]
    volume = filter(lambda v: '/var/lib/postgresql/data' in v, compose['services']['postgres']['volumes'])[0]
    volume = volume.split(":")[0]
    # append the current path
    ODOO_HOME = os.getenv("ODOO_HOME")[1:].replace("/", "_")
    volume = ODOO_HOME + "_" + volume
    if full:
        volume = os.path.join(_get_docker_volume_dir(), volume)
    click.echo(volume)
    return volume

@sync.command(name="download")
@click.argument("area", required=False)
@pass_config
@click.pass_context
def download(ctx, config, area):
    """
    help: Area defined in .access/config e.g. 'prod'
    """
    if not area:
        click.echo("Following areas available:")
        for area in get_areas():
            click.echo(area)
        sys.exit(0)
    access_config = get_config(area)

    remote_path = __exec_remote_odoo_get_string(access_config, 'volumename', '--full', 'postgres', 'data')
    volume = ctx.invoke(volume_name, full=False, service='postgres', local_path='/var/lib/postgresql/data')

    # get remote path

    __dc(['kill'] + ['postgres'])
    params = {}
    params.update(locals())
    params.update(access_config)
    args = [
        '-v',
        '{volume}:/dest'.format(**params),
        '-v',
        access_config['keyfile'] + ":" + '/root/.ssh/id_rsa',
        'volumesyncer',
        '/usr/bin/rsync',
        '-arP',
        '-e',
        "ssh -oStrictHostKeyChecking=no -i '/root/.ssh/id_rsa'",
        '--delete-after',
        '{host}:{remote_path}/_data/'.format(**params),
        '/dest/'
    ]
    __dcrun(args, interactive=True)
    __dc(['up', '-d'] + ['postgres'])
