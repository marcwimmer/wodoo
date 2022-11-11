from pathlib import Path
import subprocess
import inquirer
import sys
from datetime import datetime
import os
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .tools import _is_dirty
from .odoo_config import customs_dir
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import _execute_sql
from tabulate import tabulate


@cli.group(cls=AliasedGroup)
@pass_config
def talk(config): 
    pass

@talk.command()
@click.option("-M", "--module")
@click.option("-m", "--model")
@pass_config
def xmlids(config, module, model):
    conn = config.get_odoo_conn()
    where = " where 1 = 1"
    if model:
        where += f" AND model = '{model}'"
    if module:
        where += f" AND module = '{model}'"
    rows = _execute_sql(
        conn,
        sql=(
            "SELECT module, name, model, res_id from ir_model_data "
            f"{where} "
            "order by module, name, model "
        ),
        fetchall=True,
        return_columns=True,
    )
    click.secho(tabulate(rows[1], rows[0], tablefmt="fancy_grid"), fg="yellow")