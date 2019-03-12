"""
Starts docker container with restart unless-stopped
for cronjobs.

Uses the docker-compose.yml in simplebash and the configured cron container
from there.

"""
import subprocess
import time
import shutil
import hashlib
import os
import tempfile
import click
from copy import deepcopy
from datetime import datetime
from .wait.decorator import timeout
from .tools import _file2env
from .tools import __find_files
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from .tools import __dcrun
from .tools import __execute_sql
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup

def get_env():
    d = deepcopy(os.environ)
    _file2env(files['settings'], out_dict=d)
    return d

def _exec(cmd):
    command = ["/usr/local/bin/docker-compose"]
    command += ["-f", "docker-compose-cron.yml"]
    command += ["-p", os.environ['PROJECT_NAME'] + "_cron"]
    command += cmd
    subprocess.check_call(
        command,
        cwd=os.path.join("/opt/odoo/config/simplebash"),
        env=get_env(),
    )


@cli.group(cls=AliasedGroup)
@pass_config
def cron(config):
    pass

@cron.command(name="list")
@click.pass_context
def do_list(ctx):

    started = datetime.now()
    exc = None
    while True:
        if (datetime.now() - started).total_seconds() > 10:
            break
        try:
            _exec([
                'exec',
                'cron',
                "sudo", "/usr/bin/jobber", "list"
            ])
        except Exception as e:
            time.sleep(1)
            exc = e
        else:
            exc = None
            break
    if exc:
        raise exc

@cron.command(name='start')
@click.pass_context
def start(ctx):
    ctx.invoke(stop, ignore_error=True)

    _exec(['up', '-d', '--force-recreate', 'cron'])
    _exec(['logs', 'cron'])

    ctx.invoke(do_list)

    click.echo("""
        The cronjob container is started with 'restart unless-stopped policy'. So when the docker service restarts,
        the cronjob automatically starts again.

        Please restart the cronjob container, if you move the directory on the host.

        To stop the cronjobs, just execute:

        ./odoo cron stop
    """)

@cron.command(name='test-alive')
@click.pass_context
def testalive(ctx, ignore_error=False):
    with open('/host/dumps/test-alive7', 'w') as f:
        f.write('test')

@cron.command(name='stop')
@click.pass_context
def stop(ctx, ignore_error=False):
    try:
        _exec(['kill', 'cron'])
    except Exception:
        if not ignore_error:
            raise


@cron.command(name='restart')
@click.pass_context
def restart(ctx, ignore_error=False):
    ctx.invoke(stop, ignore_error=True)
    ctx.invoke(start)

@cron.command(name='log')
@click.pass_context
def logs(ctx):
    _exec(['exec', 'cron', 'sudo', '/usr/bin/jobber', 'log'])

@cron.command()
@click.pass_context
def interactive(ctx):
    click.echo("Use jobber command, e.g. jobber list, jobber test <job>")
    _exec(['exec', 'cron', 'bash'])

@cron.command(name='execute', help="Called internally to start jobber; contains waiting while loop")
def execute(*parameters):
    # read skeleton
    with open("/opt/jobber") as f:
        jobber = f.read()

    for searchpath in [
        "/etc_host/odoo",
        # dirs['machines'],
        # dirs['customs'],
    ]:
        for filepath in __find_files(
            searchpath,
            '-name',
            '*.jobber'
        ):
            to_append = __read_file(filepath)
            jobber += "\n"
            jobber += to_append
    jobber_path = os.path.join(os.environ['HOME'], ".jobber")
    with open(jobber_path, 'w') as f:
        f.write(jobber)

    # prepare the default env
    if os.getenv("PERSIST_JOBBER_ENV_VARIABLES", False):
        with open("/root/default_env.jobber", "w") as f:
            for variable in os.environ['PERSIST_JOBBER_ENV_VARIABLES'].split(","):
                variable = variable.strip()
                for k, v in os.environ.items():
                    if k == variable:
                        f.write("{}='{}'\n".format(k, v))
    os.system("sudo /usr/libexec/jobbermaster &")
    os.system("/usr/bin/jobber reload")
    os.system("sudo /usr/bin/jobber list")
    click.echo("Starting endless loop")
    while True:
        os.system("date")
        os.system("/usr/bin/jobber list")
        time.sleep(3600)
    os.system("sudo pkill -9 -f jobber")
