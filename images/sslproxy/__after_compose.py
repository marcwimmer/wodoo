import sys
from pathlib import Path
from odoo_tools import dirs
import inspect
import os
dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))

def after_compose(config, yml, globals):
    if config['RUN_SSLPROXY'] != '1':
        return

    nginx_conf = dirs['run'] / 'ssl' / 'nginx.conf'
    src = (dir / 'nginx.conf.template').read_text()
    domain = config['SSLPROXY_SUBDOMAINS'].split(",")[0] + "." + config['SSLPROXY_DOMAIN']
    src = src.replace("__DOMAIN__", domain)

    nginx_conf.parent.mkdir(parents=True, exist_ok=True)
    nginx_conf.write_text(src)

    Path(os.environ['HOST_RUN_DIR'])
