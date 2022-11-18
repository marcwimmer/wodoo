"""
configure:
HUB_URL=registry.name:port/user/project:version
"""
import yaml
from pathlib import Path
import subprocess
import sys
from datetime import datetime
import os
import click
from .tools import __dc
from .cli import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import split_hub_url, abort

@cli.group(cls=AliasedGroup)
@pass_config
def docker_registry(config):
    pass

@docker_registry.command()
@pass_config
def login(config):
    hub = split_hub_url(config)
    if not hub:
        abort("No HUB Configured - cannt login.")

    def _login():
        click.secho(f"Using {hub['username']}", fg='yellow')
        res = subprocess.check_output([
            'docker', 'login',
            f"{hub['url']}",
            '-u', hub['username'],
            '-p', hub['password'],
        ], encoding='utf-8')
        if "Login succeeded" in res:
            return True
        return False

    if _login():
        return

@docker_registry.command()
@pass_config
@click.pass_context
def regpush(ctx, config):
    ctx.invoke(login)
    tags = list(_apply_tags(config))
    for tag in tags:
        subprocess.check_call([
            "docker", "push", tag])

@docker_registry.command()
@click.argument('machines', nargs=-1)
@pass_config
@click.pass_context
def regpull(ctx, config, machines):
    ctx.invoke(login)

    if not machines:
        machines = list(yaml.load(config.files['docker_compose'].read_text())['services'])
    for machine in machines:
        click.secho(f"Pulling {machine}")
        __dc(config, ['pull', machine])

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

current_sha = None
def _get_service_tagname(config, service_name):
    global current_sha
    if not current_sha:
        if (Path(os.getcwd()) / '.git').exists():
            current_sha = subprocess.check_output([
                "git", "log", "-n1", "--pretty=%H"], encoding="utf-8").strip()
        else:
            if not config.DOCKER_IMAGE_TAG:
                abort((
                    "If you dont have a local git repository, then "
                    "please configure DOCKER_IMAGE_TAG=sha"
                ))
            current_sha = config.DOCKER_IMAGE_TAG

    hub = split_hub_url(config)
    if not hub:
        abort((
            "No HUB_URL configured."
        ))
    hub = "/".join([
        hub['url'],
        hub['prefix'],
    ])
    return f"{hub}/{service_name}:{current_sha}"

def _apply_tags(config):
    """
    Tags all containers by their name and sha of the git repository
    of the project. The production system can fetch the image by their
    sha then.
    """
    compose = yaml.load(config.files['docker_compose'].read_text())
    hub = config.hub_url
    hub = hub.split("/")
    assert config.project_name

    for service, item in compose['services'].items():
        if item.get('build'):
            expected_image_name = f"{config.project_name}_{service}"
        else:
            expected_image_name = item['image']
        tag = _get_service_tagname(config, service)
        if config.verbose:
            click.secho((
                f"Applying {tag} on {expected_image_name}"
            ), fg='yellow')
        subprocess.check_call([
            "docker", "tag", expected_image_name,
            tag])
        click.secho((
            f"Applied tag {tag} on {expected_image_name}"
        ), fg='green')
        yield tag

def _rewrite_compose_with_tags(config, yml):
    # set hub source for all images, that are built:
    for service_name, service in yml['services'].items():
        if config.HUB_URL:
            service.pop('build', None)
            service['image'] = _get_service_tagname(config, service_name)
