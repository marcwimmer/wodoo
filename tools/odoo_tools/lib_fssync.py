import inquirer
import stat
import importlib
import json
import platform
import os
import subprocess
import click
from pathlib import Path
from .myconfigparser import MyConfigParser
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup
from . import PROJECT_NAME


def _get_remote_homepath(host):
    if platform.system() in ["Linux", "Darwin"]:
        return subprocess.check_output([
            "ssh",
            '-o',
            'stricthostkeychecking=no',
            host,
            'echo',
            '$HOME'
        ]).decode('utf8').strip()

    raise NotImplementedError(platform.system())

def _setup_watchman_for_odoo_source(config, local_status_file):
    from pudb import set_trace
    set_trace()
    subprocess.check_output([
        'watchman',
        'watch-project',
        str(dirs['customs']),
    ])
    (Path(config.customs_dir) / '.watchmanconfig').write_text(json.dumps({
        "root_files": ["MANIFEST"],
        "enforce_root_files": True,
        "ignore_dirs": [".git", "__pycache__"],
        "fsevents_try_resync": True,  # MACOS specific
    }))

    info = ["trigger", str(dirs['customs']), {
        "name": "unison_odoo_src",
        "expression": ["anyof", ["match", "**/*", "wholename"]],
        "empty_on_fresh_instance": False,
        "command": [config.unison_odoo_src_exe],
        "stdin": ["name", "exists", "new", "size"],  # mode
        "append_files": False,
        "dedup_results": True
    }]
    subprocess.run(['watchman', '-j'], input=json.dumps(info), encoding='ascii')

    local_status_file.write_text(str(dirs['customs']))

def _setup_watchman_for_run_dirs(config, local_status_file):
    # synchronized dirs
    watched_dirs = [{'path': x, 'type': 'pull,push'} for x in config.fssync_run_dirs.split(",") if x]
    watched_dirs += [{'path': x, 'type': 'pull'} for x in config.fssync_run_dirs_pull.split(",") if x]
    watched_dirs += [{'path': x, 'type': 'push'} for x in config.fssync_run_dirs_push.split(",") if x]
    if not watched_dirs:
        return
    from . import HOST_RUN_DIR

    content = ["#!/bin/bash"]
    rsync_cmd_file = Path(config.unison_odoo_src_exe).parent / 'rsync_run_dir.py'

    for dir in watched_dirs:
        dir, ttype = dir['path'].strip(), dir['type']
        if not dir:
            continue
        local_status_file = local_status_file.with_suffix('.' + dir)
        watched_dir = HOST_RUN_DIR / dir
        (watched_dir / '.watchmanconfig').write_text(json.dumps({
            "root_files": [".watchmanconfig"],
            "enforce_root_files": True,
            "ignore_dirs": [".git", "__pycache__"],
            "fsevents_try_resync": True,  # MACOS specific
        }))

        params = {
            'dir': dir,
            'local_run_dir': HOST_RUN_DIR,
            'remote_host': config.FSSYNC_HOST,
            'remote_run_dir': config.FSSYNC_REMOTE_RUNDIR,
        }
        # from local to remote
        remote_dir = "{remote_host}:{remote_run_dir}/{dir}".format(**params)
        local_dir = "{local_run_dir}/{dir}".format(**params)
        if 'push' in ttype:
            content.append("rsync '{local_dir}/' '{remote_dir}/' -arP".format(**locals()))
        if 'pull' in ttype:
            content.append("rsync '{remote_dir}/' '{local_dir}/' -arP".format(**locals()))

        local_status_file.write_text(str(watched_dir))

        # setup watchman
        if 'push' in ttype:
            subprocess.check_output([
                'watchman',
                'watch-project',
                watched_dir,
            ])
            cmd = [
                'watchman',
                '--',
                'trigger',
                str(watched_dir),
                'run_dir_{}'.format(dir), # just a name
                '**/*',
                '--',
                str(rsync_cmd_file),
            ]
            subprocess.call(cmd)

    rsync_cmd_file.write_text('\n'.join(content))
    rsync_cmd_file.chmod(rsync_cmd_file.stat().st_mode | stat.S_IEXEC)
    del content


@cli.group(cls=AliasedGroup)
@pass_config
def fssync(config):
    pass


@fssync.command()
@pass_config
@click.pass_context
def stop(ctx, config):
    _clear_odoo_watches()

@fssync.command(name="config", help="Interactive config remote sync setup")
@pass_config
@click.pass_context
def do_config(ctx, config):

    questions = [
        inquirer.Confirm("main_machine", message="Is this the source code machine (odoo not executed in docker containers here)", default=True)
    ]
    main = inquirer.prompt(questions)
    user_config = MyConfigParser(files['user_settings'])
    if main['main_machine']:
        questions = [
            inquirer.Text("host", message="Host, where docker is executed", default=config.FSSYNC_HOST or "127.0.0.1"),
        ]
        setup = inquirer.prompt(questions)

        if setup['host'] != '127.0.0.1':
            click.echo("Please make sure, you have ssh access to that machine and watchman is configured there")
        user_config['FSSYNC_HOST'] = setup['host']
        user_config['FSSYNC_LISTEN_IP'] = '127.0.0.1'

        if setup['host'] == '127.0.0.1':
            user_config['FSSYNC_REMOTE_HOME'] = ""
            user_config['FSSYNC_REMOTE_RUNDIR'] = ""
            user_config['FSSYNC_RUN_DIRS'] = ""
            user_config['FSSYNC_RUN_DIRS_PULL'] = ""
            user_config['FSSYNC_RUN_DIRS_PUSH'] = ""

        else:
            # Path(os.environ['HOST_HOME']) / '.odoo' / 'run' / PROJECT_NAME
            questions = [
                inquirer.Text("remote_dir", message="Host remote odoo home (e.g. /opt/odoo, ~/odoo/)", default=config.FSSYNC_REMOTE_HOME or "~/odoo/"),
            ]
            a2 = inquirer.prompt(questions)
            remote_dir = a2['remote_dir']
            if not remote_dir.startswith("/") and not remote_dir.startswith("~"):
                remote_dir = "~/" + remote_dir
            if remote_dir.startswith("~"):
                remote_dir = remote_dir.replace("~", _get_remote_homepath(setup['host']))
            sample_run_dir = Path(remote_dir) / '.odoo' / 'run' / PROJECT_NAME.split("_")[0] # usually no .git on other side, so take just the custom name
            questions = [
                inquirer.Text("remote_run_dir", message="Host run dir", default=config.FSSYNC_REMOTE_RUNDIR or sample_run_dir),
            ]
            a = inquirer.prompt(questions)
            user_config['FSSYNC_REMOTE_HOME'] = remote_dir
            user_config['FSSYNC_REMOTE_RUNDIR'] = a['remote_run_dir']
            user_config['FSSYNC_RUN_DIRS'] = ""
            user_config['FSSYNC_RUN_DIRS_PULL'] = "odoo_outdir,postgresout"
            user_config['FSSYNC_RUN_DIRS_PUSH'] = "debug"
    else:
        user_config['FSSYNC_LISTEN_IP'] = '0.0.0.0'
    user_config.write()

    Commands.invoke(ctx, 'reload')

@fssync.command(help="Setup watchman to sync files.")
@click.argument('host', required=True, default="127.0.0.1")
@pass_config
@click.pass_context
def start(ctx, config, host):
    if not config.run_fssync:
        return

    if platform.system() in ['Linux', 'Darwin']:
        test = subprocess.check_output(["which", "unison"]).strip()
        if not test:
            click.echo("""
    Please install unison with:

    brew install unison
    """)
        test = subprocess.check_output(["which", "watchman"]).strip()
        if not test:
            click.echo("""
    Please install watchman with:

    brew install watchman
    """)
    else:
        raise NotImplementedError()

    def _get_sysctl(config, default):

        sysctl = subprocess.check_output([
            'sysctl',
            '-a',
        ]).decode('utf-8')
        v = [x for x in sysctl.split("\n") if x.strip().startswith(config)]
        if not v:
            return default
        return v[0].split(":")[1].strip()

    ctx.invoke(stop)

    _clear_odoo_watches()
    watchman_installed = _get_watchman_status_files_dir()
    _setup_watchman_for_odoo_source(config, watchman_installed / 'odoo_source')
    _setup_watchman_for_run_dirs(config, watchman_installed / 'debug_instructions')

    subprocess.call([
        'watchman',
        'watch-list',
    ])

def _get_watchman_status_files_dir():
    p = Path(os.environ['HOME']) / '.odoo' / 'watchman'
    p.mkdir(exist_ok=True)
    return p

def _clear_odoo_watches():
    """
    clear self initiated watches

    In files in host dir, the watched directories are written.
    """
    dir = _get_watchman_status_files_dir()
    dir.parent.mkdir(exist_ok=True)
    for file in dir.glob("*"):
        if file.exists():
            subprocess.call([
                'watchman',
                'watch-del',
                file.read_text()
            ])
            file.unlink()


Commands.register(start, 'fssync_start')
Commands.register(do_config, 'fssync_config')
