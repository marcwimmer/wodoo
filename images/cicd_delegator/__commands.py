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
from odoo_tools.lib_composer import internal_reload
from .tools import _askcontinue

url = "http://127.0.0.1:8889"

def _require_project(config):
    if not config.project_name:
        click.secho("Missing project name.")
        sys.exit(1)

@cli.group(cls=AliasedGroup)
@pass_config
def cicd(config):
    pass


@cicd.command()
@pass_config
def clear(config):
    _askcontinue(config)
    subprocess.check_call(
        ['docker-compose', 'down', '-v', 'mongo'],
        cwd=config.dirs['cicd_delegator']
    )
    subprocess.check_call(
        ['docker-compose', 'up', '-d', 'mongo'],
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command(name="list")
@pass_config
def do_list(config):
    reg = requests.get(url + "/sites").json()
    click.secho("Registered Sites: ", fg='green')
    for site in reg.get('sites', []):
        click.secho(f"\t{site['name']}", fg='green')

@cicd.command()
@pass_config
@click.pass_context
def unregister(ctx, config):
    reg = get_registry(config)
    reg['sites'] = [x for x in reg['sites'] if x['name'] != config.project_name]
    set_registry(config, reg)

    files = []
    files.append(config.files['project_docker_compose.home.project'])
    for file in files:
        if file.exists():
            file.unlink()

@cicd.command(help="Register new odoo")
@click.option("-d", "--desc", required=False)
@click.option("-a", "--author", required=False)
@click.option("-l", "--local", is_flag=True)
@click.option("-t", "--title")
@click.option("-b", "--git-branch")
@click.option("--git-sha")
@click.option("--initiator")
@pass_config
@click.pass_context
def register(ctx, config, desc, author, local, title, initiator, git_branch, git_sha):
    # reload current odoo
    from odoo_tools.click_config import Config
    from lib_modules import Modules

    reg = get_registry(config)
    # prepare network configuration
    update_project_configs(config, reg)
    internal_reload(
        config, config.dbname, demo=False,
        devmode=config.devmode_as_bool, headless=True, local=False,
        proxy_port=config.proxy_port, mailclient_gui_port=config.mailclient_gui_port,
    )

    reg = get_registry(config)
    reg.setdefault('sites', [])
    site = {'name': config.project_name}
    current_instance = list(filter(lambda x: x.get('branch', {}).get('branch') == git_branch, reg['sites']))
    if current_instance:
        current_instance = current_instance[-1]
    reg['sites'].append(site)
    site['date_registered'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    site['title'] = title
    site['initiator'] = initiator
    site['description'] = desc
    site['author'] = author
    site['git'] = {
        'branch': git_branch,
        'sha': git_sha,
    }
    site['enabled'] = False
    site['diff_modules'] = []
    # get the previous instance by branch
    if current_instance:
        current_sha = current_instance.get('git', {}).get('sha')
        if current_sha:
            site['diff_modules'] = Modules.get_changed_modules(current_sha)

    set_registry(config, reg)

    Commands.invoke(
        ctx,
        'up',
        daemon=True,
    )
    ctx.invoke(do_list)
    ctx.invoke(start)

@cicd.command()
@pass_config
def notify_created(config):
    _require_project(config)
    reg = get_registry(config)
    site = [x for x in reg if x['name'] == config.project_name][0]
    site['updated'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    site['enabled'] = True
    set_registry(config, reg)

@cicd.command()
@pass_config
def rebuild(config):
    subprocess.check_call([
        'docker-compose',
        'build',
        '--no-cache',
    ], cwd=config.dirs['cicd_delegator'])

# name conflict with docker
@cicd.command(name='cicd-restart')
@click.pass_context
@pass_config
def restart(config, ctx):
    ctx.invoke(stop)
    ctx.invoke(start)


@cicd.command()
@pass_config
def start(config):
    registry = get_registry(config)
    update_configs(config, registry)
    os.system(f"docker network create {config.CICD_NETWORK} 2>/dev/null")
    subprocess.check_call([
        'docker-compose',
        'build',
    ], cwd=config.dirs['cicd_delegator'])

    cmd = [
        'docker-compose',
    ]
    cmd += ['up', '-d']

    subprocess.check_call(
        cmd,
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command(name='cicd-debug')
@click.argument("machine", required=True)
@pass_config
def debug(config, machine):
    registry = get_registry(config)
    update_configs(config, registry)
    allowed = [
        'cicd_index',
        'cicd_delegator'
    ]
    if machine not in allowed:
        click.secho(f"Please use one of {','.join(allowed)}", fg='red')
        sys.exit(-1)

    subprocess.check_call(
        ['docker-compose', 'kill', machine],
        cwd=config.dirs['cicd_delegator']
    )
    subprocess.check_call([
        'docker-compose',
        'build',
        machine,
    ], cwd=config.dirs['cicd_delegator'])

    cmd = ['docker-compose', 'run', '--rm', '--service-ports', machine]

    subprocess.check_call(
        cmd,
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command(name="cicd-shell")
@pass_config
def shell(config):
    cmd = ['docker-compose', 'run', '--rm', 'cicd_test', 'bash']

    subprocess.check_call(
        cmd,
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command()
@click.argument('machine', required=False)
@pass_config
def logs(config, machine):
    cmd = ['docker-compose', 'logs', '-f']
    if machine:
        cmd += [machine]

    subprocess.check_call(
        cmd,
        cwd=config.dirs['cicd_delegator']
    )

@cicd.command()
@pass_config
def stop(config):

    proc = subprocess.Popen([
        'docker-compose',
        'kill',
    ], cwd=config.dirs['cicd_delegator'])
    proc.communicate()


def update_project_configs(config, registry):
    """
    Creates ~/.odoo/docker-compose.<project>.yml files, to add
    the cicd default network
    """
    if not config.CICD_NETWORK:
        click.secho("Please provide CICD_NETWORK parameter.", fg='red')
        sys.exit(-1)
    def_network = config.files['config/cicd_network'].read_text()
    def_network = def_network.replace(
        "__CICD_NETWORK_NAME__",
        config.CICD_NETWORK,
    )
    config.files['project_docker_compose.home.project'].write_text(def_network)

def update_configs(config, registry):
    _copy_folders(config, registry)
    _update_docker_compose(config, registry)

def _copy_folders(config, registry):
    for path in [
        'cicd_delegator',
        'cicd_tester',
        'cicd_index',

    ]:
        dest_path = config.dirs['cicd_delegator'] / path
        source = config.dirs['images'] / 'cicd_delegator' / path
        click.secho(f"Syncing folder from {source} to {dest_path}")
        sync_folder(
            source,
            dest_path,
        )

def _update_docker_compose(config, registry):
    dc = config.dirs['cicd_delegator'] / 'docker-compose.yml'
    template = (config.dirs['images'] / 'cicd_delegator' / 'docker-compose.yml').read_text()
    values = {
        "__CICD_NETWORK_NAME__": config.CICD_NETWORK,
        "__CICD_BINDING__": config.CICD_BINDING,
    }
    for k, v in values.items():
        if v is None:
            raise Exception(f"Value not set: {k}")
        template = template.replace(k, v)
    dc.write_text(template)
