#!/bin/env python3
import json
import sys
from contextlib import contextmanager
import requests
import click
import yaml
import inquirer
import os
import subprocess
from pathlib import Path
try:
    injected_globals = injected_globals # NOQA
except Exception:
    pass
from odoo_tools.lib_clickhelpers import AliasedGroup
from odoo_tools.tools import __empty_dir, __dc
from odoo_tools import cli, pass_config

@cli.group(cls=AliasedGroup)
@pass_config
def sslproxy(config):
    pass

# @sslproxy.command(help="Removes existing SSL certificates; restart to renew them")
# @pass_config
# @click.pass_context
# def clean(ctx, config):
    # path = Path(config.dirs['run']) / 'ssl'
    # __empty_dir(path, user_out=True)


@contextmanager
def proxy_conn(config):
    import sqlite3
    sqlite_filename = config.dirs['run'] / 'sslproxy' / 'data' / 'database.sqlite'
    if not sqlite_filename.exists():
        click.secho(f"Config File SSLPROXY does not exist yet. Please start the proxy! {sqlite_filename}", fg='red')
        sys.exit(-1)
    conn = sqlite3.connect(sqlite_filename)
    try:
        cr = conn.cursor()
        yield cr
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cr.close()
        conn.close()

@sslproxy.command(help="Resets proxy configuration and SSL Certificates")
@pass_config
@click.pass_context
def reset(ctx, config):
    domain = config.SSLPROXY_SUBDOMAINS.split(",")
    if not config.force:
        if not click.confirm(click.style("Removes certificates and all proxy settings/ forwards.", fg='red')):
            sys.exit(-1)

    # make file writable
    __dc([
        'run',
        'sslproxy',
        'chmod',
        '-R',
        '777',
        '/data',
    ])
    with proxy_conn(config) as cr:
        cr.execute("delete from proxy_host;")
        cr.executemany("update user set email = ?", [(config.SSLPROXY_LOGIN,)])
        cr.execute("update auth set secret = '$2b$13$b7sjc7q4IGZZrcg/eJwxfOZ1PxxrLu31A28BIv92JPtGHwec4YLIe';") # odoosslproxy

        routes = [
            {
                'host': 'odoo',
                'port': 8069,
                'domain': json.dumps(domain),
                'locations': json.dumps([
                    {
                        "path": "/longpolling",
                        "advanced_config": "",
                        "forward_scheme": "https",
                        "forward_host": "odoo",
                        "forward_port": 8072
                    },
                ])
            }
        ]
        cr.executemany("""
            insert into
                proxy_host
            (
                meta,
                owner_user_id,
                created_on,
                modified_on,
                domain_names,
                forward_host,
                forward_port,
                locations
            )
            values (
                '{{"nginx_online":true,"nginx_err":null}}',
                1,
                datetime('now', 'localtime'),
                datetime('now', 'localtime'),
                :domain,
                :host,
                :port,
                :locations
            )
        """, routes)
