import yaml
from pathlib import Path
import subprocess
import inquirer
import sys
import threading
import time
import traceback
from datetime import datetime
import shutil
import hashlib
import os
import tempfile
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .tools import __dc
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import _askcontinue
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import _is_dirty
from .odoo_config import current_customs
from .odoo_config import customs_dir
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass


@src.command()
@pass_config
def make_module(config, name):
    cwd = config.working_dir
    from .module_tools import make_module as _tools_make_module
    _tools_make_module(
        cwd,
        name,
    )

@src.command(name='update-ast')
def update_ast():
    from .odoo_parser import update_cache
    started = datetime.now()
    click.echo("Updating ast - can take about one minute")
    update_cache()
    click.echo("Updated ast - took {} seconds".format((datetime.now() - started).seconds))

@src.command()
def rmpyc():
    for file in dirs['customs'].glob("**/*.pyc"):
        file.unlink()

@src.command(name='show-addons-paths')
def show_addons_paths():
    from .odoo_config import get_odoo_addons_paths
    paths = get_odoo_addons_paths(relative=True)
    for path in paths:
        click.echo(path)

def _edit_text(file):
    editor = Path(os.environ['EDITOR'])
    subprocess.check_call("'{}' '{}'".format(
        editor,
        file
    ), shell=True)

def _needs_dev_mode(config):
    if not config.devmode:
        click.echo("In devmode - please pull yourself - only for production.")
        sys.exit(-1)


class BranchText(object):
    def __init__(self, branch):
        self.path = Path(os.environ['HOME']) / '.odoo/branch_texts' / branch
        self.branch = branch
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def get_text(self, interactive=True):
        if interactive:
            _edit_text(self.path)
        text = self.path.read_text()
        text = """{} {}""".format(self.branch, text)
        if interactive:
            click.echo(text)
            if not inquirer.prompt([inquirer.Confirm('use', default=True, message="Use this text:\n\n\n{}\n\n".format(text))])['use']:
                click.echo("Aborted")
                sys.exit(-1)
        return text

    def set_text(self, text):
        self.path.write_text(text)

    def new_text(self):
        if not self.path.exists():
            pass
        self.path.write_text("Please describe the ticket task here.\n")
        _edit_text(self.path)

@src.command(name='new-branch')
@click.argument("branch", required=True)
@pass_config
def new_branch(config, branch):
    from .odoo_config import customs_dir
    _needs_dev_mode(config)
    from git import Repo

    dir = customs_dir()
    repo = Repo(dir)
    _is_dirty(repo, True, assert_clean=True)

    # temporary store the text to retrieve it later
    active_branch = repo.active_branch.name
    if active_branch != 'master':
        if not _is_dirty(repo, True):
            repo.git.checkout('master')
        else:
            click.echo("Diverge from master required. You are on {}".format(active_branch))
            sys.exit(-1)
    repo.git.checkout('-b', branch)
    BranchText(branch).new_text()


def _get_modules():
    modules = []

    for module_path in MANIFEST()['modules']:
        branch = module_path['branch']
        path = Path(module_path['path']) # like 'common'
        for url in module_path['urls']:
            name = url.split("/")[-1].replace(".git", "")
            modules.append({
                'name': name,
                'subdir': path / name,
                'url': url.strip(),
                'branch': branch,
            })
    for x in modules:
        f = list(filter(lambda y: x['url'] == y['url'], modules))
        if len(f) > 1:
            raise Exception("Too many url exists: {}".format(x['url']))
    return modules

@src.command(help="Fetches all defined modules")
@click.argument('module', required=False)
@click.option('--oca', help="Include OCA Modules", is_flag=True)
@click.option('--depth', default="", help="Depth of git fetch for new modules")
@click.option('-T', '--not-threaded', default=False, help="", is_flag=True)
def pull(depth, module, not_threaded):
    filter_module = module
    del module
    from git import Repo
    from git import InvalidGitRepositoryError
    dir = customs_dir()
    repo = Repo(dir)
    _is_dirty(repo, True, assert_clean=True)
    subprocess.call([
        "git",
        "pull",
    ], cwd=dir)
    for module in _get_modules():
        if filter_module and module.name != filter_module:
            continue
        full_path = dir / module['subdir']
        if not str(module['subdir']).endswith("/."):
            if not full_path.parent.exists():
                full_path.parent.mkdir(exist_ok=True, parents=True)

        if not full_path.is_dir():
            cmd = [
                "git",
                "submodule",
                "add",
                "--force",
            ]
            if depth:
                cmd += [
                    '--depth',
                    str(depth),
                ]
            cmd += [
                "-b",
                module['branch'],
                module['url'],
                Path(module['subdir']),
            ]
            subprocess.check_call(cmd, cwd=dir)
            subprocess.check_call([
                "git",
                "checkout",
                module['branch'],
            ], cwd=dir / module['subdir'])
            subprocess.check_call([
                "git",
                "submodule",
                "update",
                "--init"
            ], cwd=dir / module['subdir'])
        del module

    for module in _get_modules():
        if filter_module and module.name != filter_module:
            continue
        try:
            module_dir = dir / module['subdir']
            if module_dir.exists():
                try:
                    repo = Repo(module_dir)
                except InvalidGitRepositoryError:
                    click.secho("Invalid Repo: {}".format(module['subdir']), bold=True, fg='red')
                else:
                    repo.git.checkout(module['branch'])
        except Exception:
            click.echo(click.style("Error switching submodule {} to Version: {}".format(module['name'], module['branch']), bold=True, fg="red"))
            raise
        del module

    threads = []
    try_again = []
    for module in _get_modules():
        if filter_module and module.name != filter_module:
            continue

        def _do_pull(module):
            click.echo("Pulling {}".format(module))
            try:
                subprocess.check_call([
                    "git",
                    "pull",
                    "--no-edit",
                ], cwd=dir / module['subdir'])
            except Exception:
                try_again.append(module)
        threads.append(threading.Thread(target=_do_pull, args=(module,)))
        del module
    if not not_threaded:
        [x.start() for x in threads]
        [x.join() for x in threads]
    else:
        for t in threads:
            t.start()
            t.join()

    for module in try_again:
        print(module['name'])
        subprocess.check_call([
            "git",
            "pull",
            "--no-edit",
        ], cwd=dir / module['subdir'])
        del module

@src.command(help="Pushes to allowed submodules")
@pass_config
@click.pass_context
def push(ctx, config):
    dir = customs_dir()
    click.echo("Pulling before...")
    ctx.invoke(pull)
    click.echo("Now trying to push.")
    threads = []
    for module in _get_modules():
        def _do_push(module):
            click.echo("Going to push {}".format(module))
            tries = 0
            while True:
                try:
                    subprocess.check_call([
                        "git",
                        "push",
                    ], cwd=dir / module['subdir'])
                except Exception:
                    print("Failed ")
                    time.sleep(1)
                    tries += 1
                    if tries > 5:
                        msg = traceback.format_exc()
                        click.echo(click.style(module['name'] + "\n" + msg, bold=True, fg='red'))
                        raise
                else:
                    break
        threads.append(threading.Thread(target=_do_push, args=(module,)))

    [x.start() for x in threads]
    [x.join() for x in threads]
    try:
        for module in _get_modules():
            subprocess.check_call([
                "git",
                "add",
                module['subdir']
            ], cwd=dir)
        subprocess.check_call([
            "git",
            "commit",
            '-m',
            '.',
        ], cwd=dir)
    except Exception:
        pass
    subprocess.check_call([
        "git",
        "push",
    ], cwd=dir)

@src.command()
@click.argument('branch')
@pass_config
def merge(config, branch):
    from git import Repo
    branch = _ask_deploy(config, branch)
    m = MANIFEST()

    repo = Repo(customs_dir())
    active_branch = repo.active_branch.name
    if active_branch in m['deploy'].keys():
        click.echo("Please go to feature branch.")
        sys.exit(-1)

    _is_dirty(repo, True, assert_clean=True)

    text = BranchText(active_branch).get_text()
    repo.git.checkout(branch)
    repo.git.merge(active_branch, '--squash', '--no-commit')
    repo.git.commit('-m', text)
    click.echo("On branch {} now.".format(branch))


@src.command(help="Commits changes in submodules")
def commit():
    from git import Repo
    dir = customs_dir()
    m = MANIFEST()

    repo = Repo(dir)
    branch = repo.active_branch.name
    if branch in m['not_allowed_commit_branches']:
        click.echo("Not allowed to commit on {}".format(branch))

    text = BranchText(branch).get_text()
    for module in _get_modules():
        subdir = dir / module['subdir']
        subprocess.call([
            "git",
            "checkout",
            str(module['branch']),
        ], cwd=subdir)
        subprocess.call([
            "git",
            "add",
            ".",
        ], cwd=subdir)
        subprocess.call([
            "git",
            "commit",
            "-am",
            text,
        ], cwd=subdir)
        del subdir
    subprocess.call([
        "git",
        "add",
        '.'
    ], cwd=dir)
    subprocess.call([
        "git",
        "commit",
        '-am',
        text,
    ], cwd=dir)
    subprocess.call([
        "git",
        "status",
    ], cwd=dir)

def _ask_deploy(config, branch):
    m = MANIFEST()
    try:
        m['deploy']
    except KeyError:
        click.echo("Missing key 'deploy' in Manifest.")
        click.echo("Example:")
        click.echo('"deploy": {')
        click.echo('"master": "ssh://git@git.clear-consulting.de:50004/odoo-deployments/{}.git",'.format(
            current_customs()
        ),)
        click.echo('}')
        sys.exit(-1)
    question = inquirer.List('branch', "", choices=m['deploy'].keys())
    if not branch:
        branch = inquirer.prompt([question])['branch']
    return branch

@src.command()
@click.argument("branch", required=False)
@click.option("--refetch", is_flag=True)
@click.option("-D", "--no-dirty-check", is_flag=True)
@pass_config
def pack(config, branch, refetch, no_dirty_check):
    from . import odoo_config
    from git import Repo
    m = MANIFEST()
    dir = customs_dir()
    repo = Repo(dir)
    if repo.active_branch.name not in ['master', 'stage']:
        click.secho("Must be on branch master or stage please.", bold=True, fg='red')
        sys.exit(1)
    if not no_dirty_check:
        _is_dirty(repo, True, True)

    dest_branch = branch
    branch = repo.active_branch.name
    deploy_url = m['deploy'][branch]
    folder = Path(os.environ['HOME']) / '.odoo' / 'pack_for_deploy' / 'odoo-deployments' / config.customs
    folder = folder.absolute()
    folder.parent.mkdir(parents=True, exist_ok=True)

    if refetch:
        shutil.rmtree(str(folder))

    if not folder.exists():
        subprocess.check_call([
            "git",
            "clone",
            deploy_url,
            folder.name,
        ], cwd=folder.parent)

    subprocess.check_call([
        "git",
        "pull",
    ], cwd=folder)

    def checkout(option):
        subprocess.check_call([
            "git",
            "checkout",
            option,
            dest_branch
        ], cwd=folder)
    try:
        checkout('-f')
        subprocess.call([
            "git",
            "pull",
        ], cwd=folder)
    except Exception:
        checkout('-b')
        subprocess.call([
            "git",
            "push",
            "--set-upstream",
            "origin",
            dest_branch,
        ], cwd=folder)
        subprocess.call([
            "git",
            "push",
            "--set-upstream-to=origin/{}".format(branch),
            dest_branch,
        ], cwd=folder)

    # clone to tmp directory and cleanup - remove unstaged and so on
    tmp_folder = Path(tempfile.mktemp(suffix='.'))
    try:
        subprocess.check_call([
            "rsync",
            str(odoo_config.customs_dir()) + "/",
            str(tmp_folder) + "/",
            '-ar',
            '--exclude=.pyc',
            '--exclude=.git',
            '--delete-after',
        ], cwd=odoo_config.customs_dir())

        # remove set_traces and other
        # remove ignore file to make ag find everything
        for f in [
            '.ignore',
            '.agignore',
            '.customsroot',
            '.module_paths',
            '.version',
            '.watchman_config',
            'submodules',
            'install',
            '.gitmodules',
            '.odoo.ast',
            '.idea',
        ]:
            f = tmp_folder / f
            if f.is_dir():
                shutil.rmtree(f)
            elif f.exists():
                f.unlink()
        output = subprocess.check_output(["ag", "-l", "set_trace", "-G", ".py"], cwd=tmp_folder).decode('utf-8')
        for file in output.split("\n"):
            file = tmp_folder / file
            if file.is_dir():
                continue
            if file.name.startswith("."):
                continue
            content = file.read_text()
            if 'set_trace' in content:
                content = content.replace("import pudb; set_trace()", "pass")
                content = content.replace("import pudb;set_trace()", "pass")
                content = content.split("\n")
                for i, line in enumerate(content):
                    if 'set_trace()' in line and line.strip().startswith('set_trace'):
                        content[i] = content[i].replace("set_trace()", "pass")
                content = '\n'.join(content)
                file.write_text(content)

        subprocess.check_call([
            "rsync",
            str(tmp_folder) + "/",
            str(folder) + "/",
            '-ar',
            '--exclude=.git',
            '--exclude=.pyc',
            '--delete-after',
        ], cwd=odoo_config.customs_dir())

        # remove .gitignore - could contain odoo for example
        gitignore = folder / '.gitignore'
        with gitignore.open('w') as f:
            f.write("""
*.pyc
    """)

        subprocess.call(["find", '.', "-name", "*.pyc", "-delete"], cwd=folder)

        subprocess.call(["git", "add", "."], cwd=folder)
        subprocess.call(["git", "commit", "-am 'new deployment - details found in development branch'"], cwd=folder)
        subprocess.call([
            "git",
            "push",
            "--set-upstream",
            "origin",
            branch,
        ], cwd=folder)
        subprocess.call(["git", "push"], cwd=folder)
    except Exception:
        shutil.rmtree(str(tmp_folder))
        raise


@src.command()
def show_current_ticket():
    from git import Repo
    repo = Repo(customs_dir())
    branch = repo.active_branch.name
    text = BranchText(branch).get_text(interactive=False)
    click.echo(text)

@src.command(name="update-addons-path", help="Sets addons paths in manifest file. Can be edited there (order)")
def update_addons_path():
    from .odoo_config import _identify_odoo_addons_paths
    paths = _identify_odoo_addons_paths(show_conflicts=True)
    root = customs_dir()
    paths = [str(x.relative_to(root)) for x in paths]

    m = MANIFEST()
    try:
        m['addons_paths']
    except KeyError:
        m['addons_paths'] = []
    current_paths = m['addons_paths']
    for p in paths:
        if p not in current_paths:
            current_paths.append(str(p))

    current_paths = [x for x in current_paths if x in paths]
    m['addons_paths'] = current_paths
    m.rewrite()

@src.command()
@click.argument('machines', nargs=-1)
@pass_config
def regpush(config, machines):
    if not machines:
        machines = list(yaml.load(files['docker_compose'].read_text())['services'])
    for machine in machines:
        __dc(['push', machine])

@src.command()
@click.argument('machines', nargs=-1)
@pass_config
def regpull(config, machines):
    if not machines:
        machines = list(yaml.load(files['docker_compose'].read_text())['services'])
    for machine in machines:
        __dc(['pull', machine])

@src.command()
@pass_config
def self_sign_hub_certificate(config):
    if os.getuid() != 0:
        click.secho("Please execute as root or with sudo!", bold=True, fg='red')
        sys.exit(-1)
    url = os.getenv("ODOO_HUB_URL")
    url_part = url.split(":")[0] + '.crt'
    cert_filename = Path("/usr/local/share/ca-certificates") / url_part
    with cert_filename.open("w") as f:
        proc = subprocess.Popen([
            "openssl",
            "s_client",
            "-connect",
            url,
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

@src.command()
@pass_config
def hub_login(config):
    hub = os.environ['ODOO_HUB_URL']

    def _login():
        res = subprocess.check_call([
            'docker', 'login', hub,
            '-u', os.environ['ODOO_HUB_USER'],
            '-p', os.environ['ODOO_HUB_PWD'],
        ])
        if "Login Succeeded" in res:
            return True
        return False

    try:
        if _login():
            return
    except Exception:
        click.secho("Please self sign certificate for {} with command 'self-sign-hub-certificate'".format(
            hub
        ), bold=True, fg='red')

        pass


Commands.register(pack)
