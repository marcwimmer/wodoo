import sys
import shutil
from pathlib import Path
import inspect
import os
dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))

def after_compose(config, settings, yml, globals):
    if settings['RUN_SSLPROXY'] != '1':
        return
    import click

    dest = config.dirs['run'] / 'sslproxy' / 'config.json'
    dest.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(
        config.dirs['odoo_home'] / 'images' / 'sslproxy' / 'config.json',
        dest,
    )

    click.secho(f"Default SSL Proxy credentials:", fg='green', bold=True)
    click.secho(f"user:\t\t {settings['SSLPROXY_LOGIN']}", fg='green')
    click.secho(f"password:\todoosslproxy", fg='green')
    click.secho(f"IMPORTANT:", fg='green', bold=True)
    click.secho(f"1. Please start the sslproxy once.", fg='green')
    click.secho(f"2. call odoo sslproxy reset", fg='green')

    # nginx_conf =
    # src = (dir / 'nginx.conf.template').read_text()
    # subdomains = settings.get('SSLPROXY_SUBDOMAINS', "")
    # if subdomains:
        # subdomains = subdomains.split(",")
        # if len(subdomains) > 1:
            # raise Exception("only one subdomain supported")

        # domain = subdomains[0] + "." + settings['SSLPROXY_DOMAIN']
    # else:
        # domain = settings['SSLPROXY_DOMAIN']

    # src = src.replace("__DOMAIN__", domain)

    # nginx_conf.parent.mkdir(parents=True, exist_ok=True)
    # nginx_conf.write_text(src)
