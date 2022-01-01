import yaml
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import os
import click
from .tools import __dc
from . import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import split_hub_url

@cli.group(cls=AliasedGroup)
@pass_config
def docker_registry(config):
    pass

@docker_registry.command()
@pass_config
def login(config):
    hub = split_hub_url(config)

    def _login():
        click.secho(f"Using {hub['username']} with {hub['password']}", fg='blue')
        res = subprocess.check_output([
            'docker', 'login',
            f"{hub['url']}",
            '-u', hub['username'],
            '-p', hub['password'],
        ])
        if "Login Succeeded" in res:
            return True
        return False

    try:
        if _login():
            return
    except Exception:
        click.secho(f"Please self sign certificate for {hub['url']} with command 'self-sign-hub-certificate'", bold=True, fg='red')

@docker_registry.command()
@click.argument('machines', nargs=-1)
@pass_config
def regpush(config, machines):
    if not machines:
        machines = list(yaml.load(config.files['docker_compose'].read_text())['services'])
    for machine in machines:
        click.secho(f"Pushing {machine}", fg='green', bold=True)
        __dc(['push', machine])

@docker_registry.command()
@click.argument('machines', nargs=-1)
@pass_config
def regpull(config, machines):
    if not machines:
        machines = list(yaml.load(config.files['docker_compose'].read_text())['services'])
    for machine in machines:
        click.secho(f"Pulling {machine}")
        __dc(['pull', machine])

@docker_registry.command()
@pass_config
def self_sign_hub_certificate(config):
    if os.getuid() != 0:
        click.secho("Please execute as root or with sudo! Docker service is restarted after that.", bold=True, fg='red')
        sys.exit(-1)
    hub = split_hub_url(config)
    url_part = hub['url'].split(":")[0] + '.crt'
    cert_filename = Path("/usr/local/share/ca-certificates") / url_part
    with cert_filename.open("w") as f:
        proc = subprocess.Popen([
            "openssl",
            "s_client",
            "-connect",
            hub['url'],
        ], stdin=subprocess.PIPE, stdout=f)
        proc.stdin.write(b"\n")
        proc.communicate()
    print(cert_filename)
    content = cert_filename.read_text()
    BEGIN_CERT = "-----BEGIN CERTIFICATE-----"
    END_CERT = "-----END CERTIFICATE-----"
    content = BEGIN_CERT + "\n" + content.split(BEGIN_CERT)[1].split(END_CERT)[0] + "\n" + END_CERT + "\n"
    cert_filename.write_text(content)
    click.secho("Restarting docker service...", fg='green')
    subprocess.check_call(['service', 'docker', 'restart'])
    click.secho("Updating ca certificates...", fg='green')
    subprocess.check_call(['update-ca-certificates'])
