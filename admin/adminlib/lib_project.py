import inquirer
import time
import threading
import click
import os
import inspect
import subprocess
import json
from module_tools.odoo_config import customs_dir
from lib_clickhelpers import AliasedGroup
from . import cli, pass_config, dirs, files, Commands

def __get_project_config():
    path = os.path.expanduser("/opt/external_home/.odoodev/conf.json")
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            f.write("{}")
    with open(path, 'r') as f:
        res = json.loads(f.read())
        res.setdefault('projects', [])
    return res


@cli.group(cls=AliasedGroup)
@pass_config
def project(config):
    pass

@project.command(name='list')
def project_list():
    projects = __get_project_config()['projects']
    for i, project in enumerate(projects):
        print("{}:".format(i + 1), "{}/{}".format(project['customs'], project['db']))

def project_activate(ctx, config, project):
    Commands.invoke('compose',
        customs=project['customs'],
        db=project['db'],
        demo=project['demo'],
    )
    if config.run_postgres:
        answer = inquirer.prompt([inquirer.Confirm('in_ram', message="Use In-RAM postgres?", default=config.run_postgres_in_ram)])
        if not answer:
            return
        if answer['in_ram'] != config.run_postgres_in_ram:
            Commands.invoke(ctx, 'set_setting', key="RUN_POSTGRES_IN_RAM", value="1" if answer['in_ram'] else "0")
        if answer['in_ram']:
            Commands.invoke(ctx, 'restore_db')

    Commands.invoke('dev')

@project.command(name='new')
@pass_config
@click.pass_context
def project_new(ctx, config):
    ans = inquirer.prompt([
        inquirer.Text('customs', message="Customs"),
        inquirer.Text('db', message="DB (if empty same as customs then)", ),
        inquirer.Confirm('demo', message="Activate demo data?"),
    ])
    if not ans:
        return
    pconfig = __get_project_config()
    project = {
        'customs': ans['customs'],
        'db': ans['db'],
        'demo': ans['demo'],
    }
    pconfig['projects'].append(project)
    __set_project_config(pconfig)
    project_activate(ctx, config, project=project)

@project.command(name='delete')
def project_delete():
    choices = map(lambda p: "/".join([p['customs'], p['db']]))
    answer = inquirer.prompt([inquirer.List("project", "Choose a project", choices=choices)])
    if not answer:
        return
    customs, db = answer['project'].split("/")
    config = __get_project_config()
    project = filter(lambda x: x['customs'] == customs and x['db'] == db, config['projects'])[0]
    config['projects'].remove(project)
    __set_project_config(config)

@project.command(name='switch')
@pass_config
@click.pass_context
def project(ctx, config):
    projects = __get_project_config()['projects']
    choices = map(lambda p: "/".join([p['customs'], p['db']]), projects)
    answer = inquirer.prompt([inquirer.List("project", "Choose a project", choices=choices)])
    if not answer:
        return

    customs, db = answer['project'].split("/")
    project = filter(lambda x: x['customs'] == customs and x['db'] == db, projects)[0]
    project_activate(ctx, config, project)

def __set_project_config(content):
    path = os.path.expandvars("/opt/external_home/.odoodev/conf.json")
    with open(path, 'w') as f:
        f.write(json.dumps(content))
