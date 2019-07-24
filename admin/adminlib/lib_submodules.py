from pathlib import Path
import traceback
import time
import threading
import click
import os
import sys
import inspect
import subprocess
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import current_version
from module_tools.odoo_config import MANIFEST
from .lib_clickhelpers import AliasedGroup
from .tools import __system
from .tools import __assert_file_exists
from . import cli, pass_config, dirs, files
from . import Commands

@cli.group(cls=AliasedGroup)
@pass_config
def submodules(config):
    pass


pushable_urls = [
    'git.clear-consulting.de',
    'git.itewimmer.de',
]

def _get_modules(include_oca=True):
    modules = []
    v = str(current_version())
    if include_oca:
        OCA_PATH = customs_dir() / 'OCA'
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
                'subdir': path,
                'url': url.strip(),
                'branch': branch,
            })
    for x in modules:
        f = list(filter(lambda y: x['url'] == y['url'], modules))
        if len(f) > 1:
            raise Exception("Too many url exists: {}".format(x['url']))
    return modules


@submodules.command(help="Fetches all defined modules")
@click.option('--oca', help="Include OCA Modules", is_flag=True)
@click.option('--depth', default="", help="Depth of git fetch for new modules")
def pull(oca, depth):
    dir = customs_dir()
    __system([
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

    for module in _get_modules():
        print(module['name'])
        try:
            subprocess.check_call([
                "git",
                "checkout",
                module['branch'],
            ], cwd=dir / module['subdir'])
        except Exception:
            click.echo(click.style("Error switching submodule {} to Version: {}".format(module['name'], module['branch']), bold=True, fg="red"))
            raise

    threads = []
    for module in _get_modules():
        def _do_pull(module):
            click.echo("Pulling {}".format(module))
            tries = 0
            while True:
                try:
                    subprocess.check_call([
                        "git",
                        "pull",
                        "--no-edit",
                    ], cwd=dir / module['subdir'] / module['name'])
                except Exception:
                    time.sleep(1)
                    tries += 1
                    if tries > 3:
                        msg = traceback.format_exc()
                        click.echo(click.style(module['name'] + "\n" + msg, bold=True, fg='red'))
                        raise
                else:
                    break
        threads.append(threading.Thread(target=_do_pull, args=(module,)))
    [x.start() for x in threads]
    [x.join() for x in threads]

@submodules.command(help="Pushes to allowed submodules")
@pass_config
@click.pass_context
def push(ctx, config):
    dir = customs_dir()
    click.echo("Pulling before...")
    ctx.invoke(pull)
    click.echo("Now trying to push.")
    threads = []
    for module in filter(lambda module: any(allowed in module['url'] for allowed in pushable_urls), _get_modules()):
        def _do_push(module):
            click.echo("Going to push {}".format(module))
            tries = 0
            while True:
                try:
                    __system([
                        "git",
                        "push",
                    ], cwd=dir / module['subdir'] / module['name'])
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
            __system([
                "git",
                "add",
                module['subdir'] / module['name']
            ], cwd=dir)
        __system([
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

@submodules.command(help="Commits changes in submodules")
@click.argument("msg", required=True)
def commit(msg):
    dir = customs_dir()
    for module in _get_modules():
        subprocess.call([
            "git",
            "checkout",
            module['version'],
        ], cwd=dir / module['subdir'] / module['name'])
        subprocess.call([
            "git",
            "add",
            ".",
        ], cwd=dir / module['subdir'] / module['name'])
        subprocess.call([
            "git",
            "commit",
            "-am",
            msg,
        ], cwd=dir / module['subdir'] / module['name'])
    subprocess.call([
        "git",
        "add",
        '.'
    ], cwd=dir)
    subprocess.call([
        "git",
        "commit",
        '-am',
        "update submodules",
    ], cwd=dir)
    print("--------------------")
    subprocess.call([
        "git",
        "status",
    ], cwd=dir)

@submodules.command(help="Displays diff in submodules")
def diff():
    DEVNULL = open(os.devnull, 'wb')
    dir = customs_dir()
    for module in _get_modules():
        module_path = dir / module['subdir'] / module['name']
        if not module_path.is_dir():
            continue
        untracked = '\n'.join(filter(lambda line: not line.endswith(".pyc"), __system([
            "git",
            "ls-files",
            "-o"
        ], cwd=module_path).strip().split("\n")))
        if untracked:
            print(module['name'])
            print("Untracked: ")
            print(untracked)
        try:
            subprocess.check_call([
                "git",
                "diff",
                "--quiet"
            ], cwd=module_path, stderr=DEVNULL)
        except Exception:
            if not untracked:
                print(module['name'])
            subprocess.call([
                "git",
                "diff",
            ], cwd=module_path)

@submodules.command(name='list-subtrees')
def list_subtrees():
    for x in __get_all_subtrees():
        click.echo(x)

def pull_push_all(ctx, mode):
    if mode == 'pull':
        todo = pull
    else:
        todo = push
    for mod in __get_all_subtrees():
        if mod.startswith("common/"):
            path = dirs['customs'] / mod
            if path.is_dir():
                mod = mod[len("common/"):]
                ctx.invoke(todo, submodule=mod)
    extra_installs = dirs['odoo_home'] / 'extra_install' / 'module'
    if extra_installs.exists():
        data = eval(extra_installs.read_text())
        for mod in data.keys():
            ctx.invoke(todo, submodule=mod, is_extra_install=True)

def __get_all_subtrees():
    res = __system([
        'git',
        'log',
    ], cwd=dirs['customs'], suppress_out=True)
    for line in res.split("\n"):
        if 'git-subtree-dir' in line:
            path = line.split(":")[-1].strip()
            yield path # e.g. common/module1

@submodules.command(name='add')
@click.argument('modules', nargs=-1, required=True)
@pass_config
def submodule_add(config, modules):
    if not modules:
        click.echo("Please provide some modules!")
        sys.exit(-1)
    __assert_file_exists(dirs['customs'], '.git')
    __assert_file_exists(dirs['customs'], 'common')

    for submodule in modules:
        __system([
            'git',
            'submodule',
            'add',
            '-b',
            str(config.odoo_version),
            '--',
            'ssh://git@git.clear-consulting.de:50004/odoo/modules/{}'.format(submodule),
            'common/{}'.format(submodule),
        ], cwd=dirs['customs'])

@submodules.command(name='publish-all')
@pass_config
@click.pass_context
def publish_all(ctx, config):
    ctx.invoke(commit, msg="Publish current version")
    ctx.invoke(push)
    Commands.invoke(ctx, 'pack')
