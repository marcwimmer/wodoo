import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __replace_in_file
from .tools import _sanity_check
from .tools import __get_odoo_commit
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def setup(config):
    pass

@setup.command()
@pass_config
def sanity_check(config):
    _sanity_check(config)
