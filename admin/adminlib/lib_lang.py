import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __find_files
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from .tools import __dcrun
from .tools import __execute_sql
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def lang(config):
    pass

@lang.command(name='export')
@click.argument('lang', required=True)
@click.argument('modules', nargs=-1, required=True)
def export_i18n(lang, modules):
    modules = ','.join(modules)
    __dcrun(['odoo', '/export_i18n.sh', lang, modules])
    # file now is in $DIR/run/i18n/export.po

@lang.command(name='list')
@pass_config
def get_all_langs(config):
    langs = [x[0] for x in __execute_sql(
        user=config.db_user,
        pwd=config.db_pwd,
        host=config.db_host,
        port=config.db_port,
        sql="select distinct code from res_lang;",
        fetchall=True
    )]
    for lang in sorted(langs):
        click.echo(lang)
    return langs

@lang.command(name='import')
@click.argument('lang', required=False)
@click.argument('po-file-path', required=True)
def lang_import_i18n(lang, po_file_path):
    __dcrun(['odoo', '/import_i18n.sh', lang, po_file_path])
