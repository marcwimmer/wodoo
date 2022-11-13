import click
from .tools import __dcrun
from .tools import __dcexec
from .tools import _execute_sql
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup


@cli.group(cls=AliasedGroup)
@pass_config
def lang(config):
    pass


@lang.command(name="export")
@click.argument("lang", required=True)
@click.argument("modules", nargs=-1, required=True)
def export_i18n(lang, modules):
    modules = ",".join(modules)
    __dcexec(config, ["odoo", "/odoolib/export_i18n.py", lang, modules])


@lang.command(name="list")
@pass_config
def get_all_langs(config):
    conn = config.get_odoo_conn()
    langs = [
        x[0]
        for x in _execute_sql(
            conn,
            sql="select distinct code from res_lang where active=true;",
            fetchall=True,
        )
    ]
    for lang in sorted(langs):
        click.echo(lang)
    return langs


@lang.command(name="import")
@click.argument("lang", required=False)
@click.argument("po-file-path", required=True)
def lang_import_i18n(lang, po_file_path):
    __dcrun(config, ["odoo", "/odoolib/import_i18n.py", lang, po_file_path])
