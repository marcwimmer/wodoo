#!/bin/env python3
import uuid
from datetime import datetime
import shutil
import json
import sys
from contextlib import contextmanager
import requests
import click
import yaml
import inquirer
import os
import subprocess
from pathlib import Path
try:
    injected_globals = injected_globals # NOQA
except Exception:
    pass
from odoo_tools.lib_clickhelpers import AliasedGroup
from odoo_tools.tools import __empty_dir, __dc, sync_folder
from odoo_tools import cli, pass_config

@cli.group(cls=AliasedGroup)
@pass_config
def cicd(config):
    pass

def get_registry(config):
    path = config.files['cicd_delegator_registry']
    result = {}
    if not path.exists():
        result = {}
    else:
        result = json.loads(path.read_text())
    result.setdefault('network_name', f'cicd_default_{uuid.uuid4().hex}')
    return result

def set_registry(config, values):
    path = config.files['cicd_delegator_registry']
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(values))

    update_nginx_configs(config, values)
    update_project_configs(config, values)

@cicd.command()
@pass_config
def clear(config):
    set_registry(config, {})

@cicd.command(name="list")
@pass_config
def do_list(config):
    click.secho("Registered Sites: ", fg='green')
    reg = get_registry(config)
    for site in reg.get('sites', []):
        click.secho(f"\t{site['name']}", fg='green')

@cicd.command(help="Register new odoo")
@pass_config
@click.pass_context
def register(ctx, config):
    reg = get_registry(config)
    reg.setdefault('sites', [])
    odoo_project_name = config.PROJECT_NAME
    existing = [x for x in reg['sites'] if x['name'] == odoo_project_name]
    if existing:
        existing = existing[0]
    else:
        site = {'name': odoo_project_name}
        reg['sites'].append(site)
        existing = site
    existing['updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_registry(config, reg)
    ctx.invoke(do_list)

@cicd.command()
@pass_config
def rebuild(config):
    subprocess.check_call([
        'docker-compose',
        'build',
        '--no-cache',
    ], cwd=config.dirs['cicd_delegator'])

@cicd.command()
@click.argument('odoo-project-name', required=True)
@pass_config
def start(config):
    subprocess.check_call([
        'docker-compose',
        'build',
    ], cwd=config.dirs['cicd_delegator'])
    subprocess.check_call([
        'docker-compose',
        'up',
        '-d',
    ], cwd=config.dirs['cicd_delegator'])

@cicd.command()
@click.argument('odoo-project-name', required=True)
@contextmanager
@pass_config
def stop(config, context):

    subprocess.check_call([
        'docker-compose',
        'kill',
    ], cwd=config.dirs['cicd_delegator'])


def update_project_configs(config, registry):
    """
    Creates ~/.odoo/docker-compose.<project>.yml files, to add
    the cicd default network
    """
    def_network = config.files['config/cicd_network'].read_text()
    def_network = def_network.replace(
        "__CICD_NETWORK_NAME__",
        registry['network_name'],
    )
    config.files['project_docker_compose.home.project'].write_text(def_network)

def update_nginx_configs(config, registry):
    _copy_index_webapp(config, registry)

    _update_docker_compose(config, registry)
    _update_nginx_conf(config, registry)
    _update_locations_and_upstreams(config, registry)


def _copy_index_webapp(config, registry):
    dest_path = config.dirs['cicd_delegator'] / 'registry_webserver'
    sync_folder(
        config.dirs['images'] / 'cicd_delegator' / 'registry_webserver',
        dest_path,
    )

def _update_docker_compose(config, registry):
    dc = config.dirs['cicd_delegator'] / 'docker-compose.yml'
    template = (config.dirs['images'] / 'cicd_delegator' / 'docker-compose.yml').read_text()
    template = template.replace(
        "__CICD_NETWORK_NAME__",
        registry['network_name'],
    )
    dc.write_text(template)

def _update_nginx_conf(config, registry):
    nginx_conf = config.dirs['cicd_delegator'] / 'nginx.conf'
    template = config.dirs['images'] / 'cicd_delegator' / 'nginx.conf'
    nginx_conf.write_text(template.read_text())

def _update_locations_and_upstreams(config, registry):
    template_upstream = (config.dirs['images'] / 'cicd_delegator' / 'nginx.upstream.template.conf').read_text()
    template_location = (config.dirs['images'] / 'cicd_delegator' / 'nginx.location.template.conf').read_text()

    locations, upstreams = [], []

    for site in registry['sites']:
        settings = {
            "__PROJECT_NAME__": site['name'],
            "__CICD_NETWORK_NAME__": registry['network_name'],
        }
        for k, v in settings.items():
            upstream = template_upstream.replace(k, v)
            location = template_location.replace(k, v)

        upstreams.append(upstream)
        locations.append(location)

    (config.dirs['cicd_delegator'] / 'nginx.upstreams.conf').write_text(
        '\n\n'.join(upstreams)
    )
    (config.dirs['cicd_delegator'] / 'nginx.locations.conf').write_text(
        '\n\n'.join(locations)
    )
