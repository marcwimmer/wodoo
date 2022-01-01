from pathlib import Path
import subprocess
import inquirer
import sys
from datetime import datetime
import os
import click
from .odoo_config import current_version
from .odoo_config import MANIFEST
from .tools import _is_dirty
from .odoo_config import customs_dir
from . import cli, pass_config
from .lib_clickhelpers import AliasedGroup
from .tools import split_hub_url

@cli.group(cls=AliasedGroup)
@pass_config
def src(config): 
    pass


@src.command()
@pass_config
@click.option('-n', '--name', required=True)
@click.option('-p', '--parent-path', required=False)
def make_module(config, name, parent_path):
    cwd = parent_path or config.working_dir
    from .module_tools import make_module as _tools_make_module
    _tools_make_module(
        cwd,
        name,
    )

@src.command(name='update-ast')
@click.option('-f', '--filename', required=False)
def update_ast(filename):
    from .odoo_parser import update_cache
    started = datetime.now()
    click.echo("Updating ast - can take about one minute")
    update_cache(filename or None)
    click.echo("Updated ast - took {} seconds".format((datetime.now() - started).seconds))

@src.command('goto-inherited')
@click.option('-f', '--filepath', required=True)
@click.option('-l', '--lineno', required=True)
def goto_inherited(filepath, lineno):
    from .odoo_parser import goto_inherited_view
    lineno = int(lineno)
    filepath = customs_dir() / filepath
    lines = filepath.read_text().split('\n')
    filepath, lineno = goto_inherited_view(filepath, lineno, lines)
    if filepath:
        print(f"FILEPATH:{filepath}:{lineno}")

@src.command()
@pass_config
def rmpyc(config):
    for file in config.dirs['customs'].glob("**/*.pyc"):
        file.unlink()

@src.command(name='show-addons-paths')
def show_addons_paths():
    from .odoo_config import get_odoo_addons_paths
    paths = get_odoo_addons_paths(relative=True)
    for path in paths:
        click.echo(path)
        
@src.command(name='make-modules', help="Puts all modules in /modules.txt")
@pass_config
def show_addons_paths(config):
    modules = ','.join(MANIFEST()['install'])
    (config.dirs['customs'] / 'modules.txt').write_text(modules)
    click.secho(f"Updated /modules.txt with: \n\n", fg='yellow')
    click.secho(modules)

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

# @src.command(help="Fetches all defined modules")
# @click.argument('module', required=False)
# @click.option('--depth', default="", help="Depth of git fetch for new modules")
# @click.option('-T', '--not-threaded', default=False, help="", is_flag=True)
# def pull(depth, module, not_threaded):
    # filter_module = module
    # del module
    # from git import Repo
    # from git import InvalidGitRepositoryError
    # dir = customs_dir()
    # repo = Repo(dir)
    # _is_dirty(repo, True, assert_clean=True)
    # subprocess.call([
        # "git",
        # "pull",
    # ], cwd=dir)
    # for module in _get_modules():
        # if filter_module and module.name != filter_module:
            # continue
        # full_path = dir / module['subdir']
        # if not str(module['subdir']).endswith("/."):
            # if not full_path.parent.exists():
                # full_path.parent.mkdir(exist_ok=True, parents=True)

        # if not full_path.is_dir():
            # cmd = [
                # "git",
                # "submodule",
                # "add",
                # "--force",
            # ]
            # if depth:
                # cmd += [
                    # '--depth',
                    # str(depth),
                # ]
            # cmd += [
                # "-b",
                # module['branch'],
                # module['url'],
                # Path(module['subdir']),
            # ]
            # subprocess.check_call(cmd, cwd=dir)
            # subprocess.check_call([
                # "git",
                # "checkout",
                # module['branch'],
            # ], cwd=dir / module['subdir'])
            # subprocess.check_call([
                # "git",
                # "submodule",
                # "update",
                # "--init"
            # ], cwd=dir / module['subdir'])
        # del module

    # for module in _get_modules():
        # if filter_module and module.name != filter_module:
            # continue
        # try:
            # module_dir = dir / module['subdir']
            # if module_dir.exists():
                # try:
                    # repo = Repo(module_dir)
                # except InvalidGitRepositoryError:
                    # click.secho("Invalid Repo: {}".format(module['subdir']), bold=True, fg='red')
                # else:
                    # repo.git.checkout(module['branch'])
        # except Exception:
            # click.echo(click.style("Error switching submodule {} to Version: {}".format(module['name'], module['branch']), bold=True, fg="red"))
            # raise
        # del module

    # threads = []
    # try_again = []
    # for module in _get_modules():
        # if filter_module and module.name != filter_module:
            # continue

        # def _do_pull(module):
            # click.echo("Pulling {}".format(module))
            # try:
                # subprocess.check_call([
                    # "git",
                    # "pull",
                    # "--no-edit",
                # ], cwd=dir / module['subdir'])
            # except Exception:
                # try_again.append(module)
        # threads.append(threading.Thread(target=_do_pull, args=(module,)))
        # del module
    # if not not_threaded:
        # [x.start() for x in threads]
        # [x.join() for x in threads]
    # else:
        # for t in threads:
            # t.start()
            # t.join()

    # for module in try_again:
        # print(module['name'])
        # subprocess.check_call([
            # "git",
            # "pull",
            # "--no-edit",
        # ], cwd=dir / module['subdir'])
        # del module

# @src.command(help="Pushes to allowed submodules")
# @pass_config
# @click.pass_context
# def push(ctx, config):
    # dir = customs_dir()
    # click.echo("Pulling before...")
    # ctx.invoke(pull)
    # click.echo("Now trying to push.")
    # threads = []
    # for module in _get_modules():
        # def _do_push(module):
            # click.echo("Going to push {}".format(module))
            # tries = 0
            # while True:
                # try:
                    # subprocess.check_call([
                        # "git",
                        # "push",
                    # ], cwd=dir / module['subdir'])
                # except Exception:
                    # print("Failed ")
                    # time.sleep(1)
                    # tries += 1
                    # if tries > 5:
                        # msg = traceback.format_exc()
                        # click.echo(click.style(module['name'] + "\n" + msg, bold=True, fg='red'))
                        # raise
                # else:
                    # break
        # threads.append(threading.Thread(target=_do_push, args=(module,)))

    # [x.start() for x in threads]
    # [x.join() for x in threads]
    # try:
        # for module in _get_modules():
            # subprocess.check_call([
                # "git",
                # "add",
                # module['subdir']
            # ], cwd=dir)
        # subprocess.check_call([
            # "git",
            # "commit",
            # '-m',
            # '.',
        # ], cwd=dir)
    # except Exception:
        # pass
    # subprocess.check_call([
        # "git",
        # "push",
    # ], cwd=dir)


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
@pass_config
def setup_venv(config):
    dir = customs_dir()
    os.chdir(dir)
    venv_dir = dir / '.venv'
    gitignore = dir / '.gitignore'
    if '.venv' not in gitignore.read_text().split("\n"):
        with gitignore.open("a") as f:
            f.write("\n.venv\n")

    subprocess.check_call(["python3", "-m", "venv", venv_dir.absolute()])

    click.secho("Please execute following commands in your shell:", bold=True)
    click.secho("source '{}'".format(venv_dir / 'bin' / 'activate'))
    click.secho("pip3 install cython")
    click.secho("pip3 install -r https://raw.githubusercontent.com/odoo/odoo/{}/requirements.txt".format(current_version()))
    requirements1 = Path(__file__).parent.parent / 'images' / 'odoo' / 'config' / str(current_version()) / 'requirements.txt'
    click.secho("pip3 install -r {}".format(requirements1))