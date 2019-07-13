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
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from . import cli, pass_config, dirs, files, Commands
from lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def telegram(config):
    pass


@telegram.command()
@pass_config
def telegram_setup(config):
    """
    helps creating a permanent chatid
    """
    if config.telegram_enabled == "1":
        os.system("""
cd "{dir}"
docker-compose run -it telegrambat /setup.sh
""".format(dir=dirs['telegrambot']))

@telegram.command(name='send')
@pass_config
def telegram_send(config, message):
    if config.telegram_enabled:
        os.system("""
            cd "{dir}"
            docker-compose run telegrambat /send.py "{message}"
        """.format(
            dir=dirs['telegrambot'],
            message=message,
        ))


Commands.register(telegram_send)
