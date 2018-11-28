import time
import threading
import click
import os
import sys
import inspect
import subprocess
from module_tools.odoo_config import customs_dir
from lib_clickhelpers import AliasedGroup
from tools import __system
from tools import __assert_file_exists
from . import cli, pass_config, dirs, files

@cli.group(cls=AliasedGroup)
@pass_config
def submodules(config):
    pass


pushable_urls = [
    'git.clear-consulting.de',
    'git.itewimmer.de',
]

def _get_modules():
    modules = []
    with open(os.path.join(customs_dir(), 'submodules')) as f:
        content = f.read()
        for line in content.split("\n"):
            if not line:
                continue
            version, dir, url = line.split(":", 2)
            if dir == '.':
                dir = ''
            data = {
                'name': os.path.basename(url).strip(),
                'subdir': os.path.join('common', dir),
                'url': url.strip(),
                'version': version,
            }
            if filter(lambda module: module['name'] == data['name'] and module['url'] == data['url'], modules):
                raise Exception("Already exists: {}".format(data))
            modules.append(data)
    return modules


@submodules.command(help="Fetches all defined modules")
def pull():
    dir = customs_dir()
    subprocess.check_output([
        "git",
        "pull",
    ], cwd=os.path.join(dir))
    for module in _get_modules():
        full_path = os.path.join(dir, module['subdir'], module['name'])
        if not module['subdir'].endswith("/."):
            if not os.path.exists(os.path.dirname(full_path)):
                os.makedirs(os.path.dirname(full_path))

        if not os.path.isdir(full_path):
            subprocess.check_call([
                "git",
                "submodule",
                "add",
                "--force",
                "-b",
                module['version'],
                module['url'],
                os.path.join(module['subdir'], module['name']),
            ], cwd=dir)
            subprocess.check_call([
                "git",
                "checkout",
                module['version'],
            ], cwd=os.path.join(dir, module['subdir'], module['name']))
            subprocess.check_call([
                "git",
                "submodule",
                "update",
                "--init"
            ], cwd=os.path.join(dir, module['subdir'], module['name']))

    for module in _get_modules():
        print(module['name'])
        subprocess.check_call([
            "git",
            "checkout",
            module['version'],
        ], cwd=os.path.join(dir, module['subdir'], module['name']))

    threads = []
    for module in _get_modules():
        def _do_pull(module):
            tries = 0
            while True:
                try:
                    subprocess.check_call([
                        "git",
                        "pull",
                        "--no-edit",
                    ], cwd=os.path.join(dir, module['subdir'], module['name']))
                except Exception:
                    time.sleep(1)
                    tries += 1
                    if tries > 3:
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
            tries = 0
            while True:
                try:
                    subprocess.check_output([
                        "git",
                        "push",
                    ], cwd=os.path.join(dir, module['subdir'], module['name']))
                except Exception:
                    from pudb import set_trace
                    set_trace()
                    time.sleep(1)
                    tries += 1
                    if tries > 5:
                        click.echo(click.style(module['name'], bold=True, color='red'))
                        raise
                else:
                    break
    threads.append(threading.Thread(target=_do_push, args=(module,)))

    [x.start() for x in threads]
    [x.join() for x in threads]
    try:
        for module in _get_modules():
            subprocess.check_output([
                "git",
                "add",
                os.path.join(module['subdir'], module['name']),
            ], cwd=os.path.join(dir))
        subprocess.check_output([
            "git",
            "commit",
            '-m',
            '.',
        ], cwd=os.path.join(dir))
    except Exception:
        pass
    subprocess.check_call([
        "git",
        "push",
    ], cwd=os.path.join(dir))

@submodules.command(help="Commits changes in submodules")
@click.argument("msg", required=True)
def commit(msg):
    dir = customs_dir()
    for module in _get_modules():
        subprocess.check_call([
            "git",
            "checkout",
            module['version'],
        ], cwd=os.path.join(dir, module['subdir'], module['name']))
        subprocess.check_call([
            "git",
            "add",
            ".",
        ], cwd=os.path.join(dir, module['subdir'], module['name']))
        subprocess.Popen([
            "git",
            "commit",
            "-am",
            msg,
        ], cwd=os.path.join(dir, module['subdir'], module['name'])).wait()
    subprocess.Popen([
        "git",
        "add",
        '.'
    ], cwd=os.path.join(dir)).wait()
    subprocess.Popen([
        "git",
        "commit",
        '-am',
        "update submodules",
    ], cwd=os.path.join(dir)).wait()
    print("--------------------")
    subprocess.Popen([
        "git",
        "status",
    ], cwd=os.path.join(dir)).wait()

@submodules.command(help="Displays diff in submodules")
def diff():
    DEVNULL = open(os.devnull, 'wb')
    dir = customs_dir()
    for module in _get_modules():
        module_path = os.path.join(dir, module['subdir'], module['name'])
        if not os.path.isdir(module_path):
            continue
        untracked = '\n'.join(filter(lambda line: not line.endswith(".pyc"), subprocess.check_output([
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
            subprocess.Popen([
                "git",
                "diff",
            ], cwd=module_path).wait()

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
            path = os.path.join(dirs['customs'], mod)
            if os.path.isdir(path):
                mod = mod[len("common/"):]
                ctx.invoke(todo, submodule=mod)
    extra_installs = os.path.join(dirs['odoo_home'], 'extra_install', 'module')
    if os.path.exists(extra_installs):
        with open(extra_installs, 'r') as f:
            data = eval(f.read())
        for mod in data.keys():
            ctx.invoke(todo, submodule=mod, is_extra_install=True)

@submodules.command(name='OCA')
@click.argument('module', nargs=-1)
@pass_config
def OCA(config, module):
    """
    Adds module from OCA - provide the repository name like 'web_modules'
    """
    from module_tools.module_tools import link_modules
    for module in module:
        for module in module.split(","):
            wd = dirs['customs']
            if not os.path.exists(os.path.join(wd, 'OCA')):
                os.mkdir(os.path.join(wd, 'OCA'))
            __system([
                'git',
                'submodule',
                'add',
                '-b',
                str(config.odoo_version),
                '--',
                'https://github.com/OCA/{}.git'.format(module),
                'OCA/{}'.format(module),
            ], cwd=wd)
            click.echo("Added submodule {}".format(module))
    link_modules()

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
    __assert_file_exists(os.path.join(dirs['customs'], '.git'))
    __assert_file_exists(os.path.join(dirs['customs'], 'common'))

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
