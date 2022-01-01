import sys
import re
import base64
import click
import yaml
import inspect
import os
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

def after_compose(config, settings, yml, globals):
    from odoo_tools.tools import get_services
    from pathlib import Path
