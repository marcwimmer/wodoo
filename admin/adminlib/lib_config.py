import shutil
import hashlib
import os
import tempfile
import click
import tools
from tools import __assert_file_exists
from tools import __system
from tools import __safe_filename
from tools import __find_files
from tools import __read_file
from tools import __write_file
from tools import __append_line
from tools import __exists_odoo_commit
from tools import __get_odoo_commit
from lib_clickhelpers import AliasedGroup
from . import cli, pass_config, dirs, files

@cli.group(cls=AliasedGroup)
@pass_config
def module(config):
    pass
