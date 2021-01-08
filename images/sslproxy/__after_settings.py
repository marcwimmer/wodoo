import sys
import click

def after_settings(config):
    if config['RUN_SSLPROXY'] != '1':
        return

    config['RUN_PROXY_PUBLISHED'] = '0'

    if not config.get('SSLPROXY_DOMAINS', False):
        click.secho("It is possible to configure SSLPROXY_DOMAINS, comma separated list.", fg='yellow')
        click.secho("Otherwise configure the ssl proxy on your own.", fg='yellow')
