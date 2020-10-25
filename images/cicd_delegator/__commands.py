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
from odoo_tools import cli, pass_config, Commands

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
    if not values:
        return

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
@click.argument("desc", required=False)
@click.argument("author", required=False)
@pass_config
@click.pass_context
def register(ctx, config, desc, author):
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
    if desc:
        existing['description'] = desc
    if author:
        existing['author'] = author
    set_registry(config, reg)

    # reload current odoo
    Commands.invoke(
        ctx,
        'reload',
        db=odoo_project_name,
        demo=False,
        proxy_port=False,
        headless=True,
        mailclient_gui_port=False,
        local=True,
        project_name=odoo_project_name,
        devmode=True
    )
    Commands.invoke(
        ctx,
        'up',
        daemon=True,
    )
    ctx.invoke(do_list)
    ctx.invoke(start, no_daemon=False)
    ctx.invoke(reload_nginx)


@cicd.command()
@pass_config
def reload_nginx(config):
    subprocess.check_call([
        'docker-compose',
        'exec',
        'cicd_delegator',
        'nginx',
        '-s',
        'reload',
    ], cwd=config.dirs['cicd_delegator'])

@cicd.command()
@pass_config
def rebuild(config):
    subprocess.check_call([
        'docker-compose',
        'build',
        '--no-cache',
    ], cwd=config.dirs['cicd_delegator'])

@cicd.command()
@click.option("-D", "--no-daemon", is_flag=True)
@pass_config
def start(config, no_daemon):
    registry = get_registry(config)
    update_nginx_configs(config, registry)
    subprocess.check_call([
        'docker-compose',
        'build',
        'cicd_index',
    ], cwd=config.dirs['cicd_delegator'])

    cmd = [
        'docker-compose',
        'up',
    ]
    if not no_daemon:
        cmd += ['-d']
    subprocess.check_call(
        cmd,
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command()
@pass_config
def stop(config):

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

    # make the empty file
    (config.dirs['cicd_delegator'] / 'empty').write_text('# disabled nginx conf')

def _update_nginx_conf(config, registry):
    nginx_conf = config.dirs['cicd_delegator'] / 'nginx.conf'
    template = (config.dirs['images'] / 'cicd_delegator' / 'nginx.conf').read_text()
    template = template.replace(
        "__PROJECT_NAMES_PIPED__",
        "|".join(x['name'] for x in registry['sites']),
    )
    nginx_conf.write_text(template)

def _update_locations_and_upstreams(config, registry):
    template_upstream = (config.dirs['images'] / 'cicd_delegator' / 'nginx.upstream.template.conf').read_text()
    template_location = (config.dirs['images'] / 'cicd_delegator' / 'nginx.location.template.conf').read_text()

    locations, upstreams = [], []

    # # get proxy container name from docker compose
    # if not config.files['docker_compose'].exists():
    # click.secho("Please reload the current branch for example with: ", fg='red')
    # click.secho("odoo reload --local --devmode --headless --project-name 'unique_name'", fg='red')
    # sys.exit(-1)

    for site in registry['sites']:
        settings = {
            "__PROJECT_NAME__": site['name'],
            "__CICD_NETWORK_NAME__": registry['network_name'],
            "__PROXY_NAME__": f"{site['name']}_{site['name']}_proxy",
        }
        upstream = template_upstream
        location = template_location
        for k, v in settings.items():
            upstream = upstream.replace(k, v)
            location = location.replace(k, v)

        upstreams.append(upstream)
        locations.append(location)

    (config.dirs['cicd_delegator'] / 'nginx.upstreams.conf').write_text(
        '\n\n'.join(upstreams)
    )
    (config.dirs['cicd_delegator'] / 'nginx.locations.conf').write_text(
        '\n\n'.join(locations)
    )
