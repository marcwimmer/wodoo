#!/bin/env python3
import requests
import click
import inquirer
import os
import subprocess
from pathlib import Path
try:
    injected_globals = injected_globals # NOQA
except Exception:
    pass
Commands = injected_globals['Commands']
__dcrun = injected_globals['__dcrun']
dirs = injected_globals['dirs']
AliasedGroup = injected_globals['AliasedGroup']
pass_config = injected_globals['pass_config']
cli = injected_globals['cli']
abort = injected_globals['abort']

@cli.group(cls=AliasedGroup)
@pass_config
def sslproxy(config):
    pass

def _safe_delete(f):
    if f.exists():
        f.unlink()

@sslproxy.command()
@click.option('--test', is_flag=True, help="Set if you're testing your setup to avoid hitting request limits")
@pass_config
@click.pass_context
def init(ctx, config, test):
    click.secho("NOT VERIFIED YET", fg='red', bold=True)
    from pudb import set_trace
    set_trace()
    if not config.sslproxy_email:
        abort("Missing SSLPROXY_EMAIL")
    if not config.sslproxy_domain:
        abort("Missing SSLPROXY_DOMAIN")

    data_path = Path(config.host_run_dir) / 'certbot'

    domains = [config.sslproxy_domain]
    rsa_key_size = 4096
    email = config.sslproxy_email

    if data_path.exists():
        if not inquirer.prompt([inquirer.Confirm('overwrite', message="Existing data found for {domains}. Continue and replace existing certificate".format(**locals()), default=True)])['overwrite']:
            abort("User aborted")

    options_ssl_nginx_conf = data_path / 'conf/options-ssl-nginx.conf'
    ssl_dhparams_pem = data_path / 'conf/ssl-dhparams.pem'
    if not options_ssl_nginx_conf.exists() or not ssl_dhparams_pem.exists():
        click.secho("Downloading recommended TLS parameters ...", fg='green')
        options_ssl_nginx_conf.parent.mkdir(exist_ok=True, parents=True)
        r = requests.get('https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/options-ssl-nginx.conf')
        r.raise_for_status()
        options_ssl_nginx_conf.write_text(r.content)

        r = requests.get('https://raw.githubusercontent.com/certbot/certbot/master/certbot/ssl-dhparams.pem')
        r.raise_for_status()
        ssl_dhparams_pem.write_text(r.content)

    click.echo("### Creating dummy certificate for {domains} ...".format(**locals()))
    certbot_config_path = dirs['run'] / 'sslproxy' / 'certbot' / 'conf'
    dummy_certs_path = certbot_config_path / 'live' / domains[0]
    dummy_certs_path.mkdir(exist_ok=True, parents=True)
    certbot_cmd = [
        'openssl',
        'req',
        '-x509',
        '-nodes',
        '-newkey',
        'rsa:1024',
        '-days 1',
        '-keyout',
        "'{path}/privkey.pem\'".format(path=dummy_certs_path),
        '-out',
        "'{path}/fullchain.pem\'".format(path=dummy_certs_path),
        '-subj',
        "'/CN=localhost\'".format(path=dummy_certs_path),
    ]
    __dcrun([
        '--rm',
        '--entrypoint "{}"'.format(certbot_cmd),
        'certbot'
    ])

    click.echo("### Starting nginx for challenge/response...")
    Commands.invoke(ctx, 'rm', machines=['sslproxy'])
    Commands.invoke(ctx, 'up', daemon=True, machines=['sslproxy'])

    click.echo("### Deleting dummy certificate for $domains ...")
    _safe_delete(certbot_config_path / 'live' / domains[0])
    _safe_delete(certbot_config_path / 'archive' / domains[0])
    _safe_delete(certbot_config_path / 'renewal' / domains[0])

    click.echo("### Requesting Let's Encrypt certificate for $domains ...")
    domain_args = " -d ".join(domains)

    # Select appropriate email arg
    email_arg = "--register-unsafely-without-email"
    if email:
        email_arg = "--email {}".format(email)

    # Enable staging mode if needed
    staging_arg = ''
    if test:
        staging_arg = '--staging'

    certbot_cmd = [
        "certbot certonly --webroot -w /var/www/certbot",
        staging_arg,
        email_arg,
        domain_args,
        '--rsa-key-size {}'.format(rsa_key_size),
        '--agree-tos',
        '--force-renewal'
    ]

    __dcrun(['--rm', '--entrypoint "{}"'.format(' '.join(certbot_cmd)), 'certbot'])
    click.secho("### Done - shutting down sslproxy - please start up then", fg='green', bold=True)
    Commands.invoke(ctx, 'kill', 'sslproxy')
