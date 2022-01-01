import click
from .tools import __dcrun
from .tools import __dcexec
from .tools import _execute_sql
from . import cli, pass_config
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
    __dcexec(['odoo', '/odoolib/export_i18n.py', lang, modules])
    # file now is in $DIR/run/i18n/export.po

@lang.command(name='list')
@pass_config
def get_all_langs(config):
    langs = [x[0] for x in _execute_sql(
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
    __dcrun(['odoo', '/import_i18n.py', lang, po_file_path])
