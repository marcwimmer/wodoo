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
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import _askcontinue
from .tools import __append_line
from .tools import __get_odoo_commit
from .odoo_config import customs_dir
from . import cli, pass_config, dirs, files, Commands
from .lib_clickhelpers import AliasedGroup

@cli.group(cls=AliasedGroup)
@pass_config
def src(config):
    pass

@src.command(name='make-customs')
@pass_config
@click.pass_context
def src_make_customs(ctx, config, customs, version):
    raise Exception("rework - add fetch sha")

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
    paths = get_odoo_addons_paths()
    for path in paths:
        click.echo(path)

def _needs_dev_mode(config):
    if not config.devmode:
        click.echo("In devmode - please pull yourself - only for production.")
        sys.exit(-1)


def _is_dirty(repo, check_submodule):
    from git import Repo
    if repo.is_dirty() or repo.untracked_files:
        return True
    if check_submodule:
        for submodule in repo.submodules:
            if _is_dirty(Repo(submodule.path), True):
                return True
    return False

class BranchText(object):
    def __init__(self, branch):
        self.path = Path(os.environ['HOME']) / '/.odoo/branch_texts' / branch
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def get_text(self):
        return self.path.read_text()

    def set_text(self, text):
        self.path.write_text(text)

@src.command(name='new-branch')
@click.argument("branch", required=True)
@pass_config
def new_branch(config, branch):
    from .odoo_config import customs_dir
    _needs_dev_mode(config)
    from git import Repo

    dir = customs_dir()
    repo = Repo(dir)
    if _is_dirty(repo, True):
        click.echo("Dirty directory - please cleanup.")
        sys.exit(-1)

    question = [
        inquirer.Text('desc', message="Description", required=True)
    ]
    ans = inquirer.prompt(question)

    # temporary store the text to retrieve it later
    BranchText(branch).set_text(ans['desc'])

    from pudb import set_trace
    set_trace()
    question = [
        inquirer.Text('desc', message="Description", default=ans['desc'])
    ]
    ans = inquirer.prompt(question)

@src.command(name='fetch', help="Walks into source code directory and pull latest branch version.")
@pass_config
def fetch_latest_revision(config):
    from .odoo_config import customs_dir
    _needs_dev_mode(config)

    subprocess.call([
        "git",
        "pull",
    ], cwd=customs_dir())

    subprocess.check_call([
        "git",
        "checkout",
        "-f",
    ], cwd=customs_dir())

    subprocess.call([
        "git",
        "status",
    ], cwd=customs_dir())

def _get_modules(include_oca=True):
    modules = []
    v = str(current_version())
    if include_oca:
        OCA_PATH = Path('addons_OCA')
        for OCA in MANIFEST()['OCA']:
            modules.append({
                'name': OCA,
                'branch': v,
                'url': 'https://github.com/OCA/{}.git'.format(OCA),
                'subdir': OCA_PATH / OCA,
            })

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
@click.option('--oca', help="Include OCA Modules", is_flag=True)
@click.option('--depth', default="", help="Depth of git fetch for new modules")
def pull(oca, depth):
    dir = customs_dir()
    subprocess.call([
        "git",
        "pull",
    ], cwd=dir)
    for module in _get_modules(include_oca=oca):
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

    for module in _get_modules(include_oca=oca):
        try:
            module_dir = dir / module['subdir']
            if module_dir.exists():
                subprocess.check_call([
                    "git",
                    "checkout",
                    str(module['branch']),
                ], cwd=module_dir)
        except Exception:
            click.echo(click.style("Error switching submodule {} to Version: {}".format(module['name'], module['branch']), bold=True, fg="red"))
            raise

    threads = []
    try_again = []
    for module in _get_modules(include_oca=oca):
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
    [x.start() for x in threads]
    [x.join() for x in threads]

    for module in try_again:
        print(module['name'])
        subprocess.check_call([
            "git",
            "pull",
            "--no-edit",
        ], cwd=dir / module['subdir'])

@src.command(help="Pushes to allowed submodules")
@pass_config
@click.pass_context
def push(ctx, config):
    dir = customs_dir()
    click.echo("Pulling before...")
    ctx.invoke(pull)
    click.echo("Now trying to push.")
    threads = []
    for module in _get_modules(include_oca=False):
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
        for module in _get_modules(include_oca=False):
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

@src.command(help="Commits changes in submodules")
def commit():
    from git import Repo
    dir = customs_dir()
    m = MANIFEST()

    repo = Repo(dir)
    branch = repo.active_branch.name
    if branch in m['not_allowed_commit_branches']:
        click.echo("Not allowed to commit on {}".format(branch))
    from pudb import set_trace
    set_trace()
    question = [
        inquirer.Text('desc', message="Description")
    ]
    ans = inquirer.prompt(question)

    text = """Ticket: {}

{}
""".format(ans['ticketnr'], ans['desc']).strip()
    for module in _get_modules(include_oca=False):
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
        "msg",
    ], cwd=dir)
    subprocess.call([
        "git",
        "status",
    ], cwd=dir)


@src.command()
@click.argument("branch", required=False)
@click.option("--refetch", is_flag=True)
@pass_config
def pack(config, branch, refetch):
    from . import odoo_config

    m = MANIFEST()
    try:
        m['deploy']
    except KeyError:
        click.echo("Missing key 'deploy' in Manifest.")
        click.echo("Example:")
        click.echo('"deploy": {')
        click.echo('"master": "ssh://git@git.clear-consulting.de:50004/odoo-deployments/sunday.git",',)
        click.echo('}')
        sys.exit(-1)
    question = inquirer.List('branch', "", choices=m['deploy'].keys())
    if not branch:
        branch = inquirer.prompt([question])['branch']
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
            branch
        ], cwd=folder)
    try:
        checkout('-f')
    except Exception:
        checkout('-b')
        subprocess.call([
            "git",
            "push",
            "--set-upstream",
            "origin",
            branch,
        ], cwd=folder)
        subprocess.call([
            "git",
            "push",
            "--set-upstream-to=origin/{}".format(branch),
            branch,
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
            print(file)
            content = file.read_text()
            if 'set_trace' in content:
                content = content.replace("import pudb; set_trace()", "pass")
                content = content.replace("import pudb;set_trace()", "pass")
                content = content.replace("set_trace()", "pass")
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


Commands.register(pack)
