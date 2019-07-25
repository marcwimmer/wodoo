import shutil
import hashlib
import os
import tempfile
import click
from tools import __assert_file_exists
from tools import __system
from tools import __safe_filename
from tools import __read_file
from tools import __write_file
from tools import __append_line
from tools import __get_odoo_commit
from . import cli, pass_config, dirs, files
from lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def ticket(config):
    pass

@ticket.command()
def deploy():
    from module_tools import odoo_versioning as versioning
    versioning.action_deploy_ticket()

@ticket.command()
def dirty():
    from module_tools import odoo_versioning as versioning
    versioning.dirty()

@ticket.command(name='inc-version')
def ticket_incversions():
    from module_tools import odoo_versioning as versioning
    versioning.actions["incversions"]()

@ticket.command(name='switch')
def switch_ticket(ticket):
    from module_tools import odoo_versioning as versioning
    versioning.actions["switch-ticket"](*[ticket])

@ticket.command()
def stage():
    from module_tools import odoo_versioning as versioning
    versioning.action_stage_ticket()

@ticket.command()
def new_ticket(ticket_name):
    from module_tools import odoo_versioning as versioning
    versioning.actions['new-ticket'](*[ticket_name])

@ticket.command()
def open_tickets(command_options):
    from module_tools import odoo_versioning as versioning
    versioning.actions["open-tickets"]()

@ticket.command()
def commit(*parameters):
    from module_tools import odoo_versioning as versioning
    versioning.actions["commit"](*parameters)

@ticket.command()
def current_ticket():
    from module_tools import odoo_versioning as versioning
    versioning.actions["current-ticket"]()
