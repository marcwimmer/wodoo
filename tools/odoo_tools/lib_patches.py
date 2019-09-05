from pathlib import Path
import sys
import re
import subprocess
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from . import odoo_config
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup


def _get_odoo_github_disk_path():
    url = Path(os.environ['GITHUB_ODOO_ON_DISK']).absolute()
    if not Path(url).exists() and not Path(url).absolute().is_dir():
        click.echo("Requires odoo on from github cloned to disk.")
        sys.exit(-1)
    return url

@cli.group(cls=AliasedGroup)
@pass_config
def patch(config):
    """

    Workflow new patch:

      * ../odoo patch prepare

      * <adapt odoo>

      * ../odoo patch preview

      *../odoo patch create <name to describe>

      *./odoo patch apply-all
    """
    M = odoo_config.MANIFEST()
    config.odoo_local_dir = 'odoo'
    config.odoo_local = dirs['customs'] / config.odoo_local_dir
    config.ignore_file = dirs['customs'] / '.gitignore'
    config.odoo_git = _get_odoo_github_disk_path()
    config.patch_dir = M.patch_dir / __get_odoo_commit()
    config.sub_git = config.odoo_local / '.git'
    odoo_dir = dirs['customs'] / 'odoo'
    __assert_file_exists(odoo_dir, isdir=True)

    config.patch_dir.mkdir(exist_ok=True)

@patch.command(name='prepare')
@pass_config
@click.pass_context
def patch_prepare(ctx, config):
    """
    makes git repo at odoo and applies default patches like remove install notifications
    """
    ctx.invoke(patch_reset)
    _patch_gitify(config)
    _patch_default_patches(config)

    subprocess.check_call(["git", "add", "."], cwd=config.odoo_local)
    subprocess.call(["git", "commit", "-qam", "removed install notifications"], cwd=config.odoo_local)
    patches = [x for x in _patch_list(config)]
    for filepath in patches:
        ctx.invoke(patch_apply, filepath=filepath)
    subprocess.check_call(["git", "add", "."], cwd=config.odoo_local)
    if patches:
        subprocess.check_call(["git", "commit", "-qam", "applied all current patches"], cwd=config.odoo_local)
    click.echo("You can now do changes; use odoo patch preview to display your changes.")

@patch.command(name='preview')
@pass_config
def patch_preview(config):
    """
    shows what is patched
    """
    diff = _patch_get_diff(config)
    filename = tempfile.mktemp(suffix='.')
    with open(filename, 'w') as f:
        f.write(diff)
    os.system('cat "{}" | colordiff'.format(filename))

@patch.command(name='create')
@click.argument('name', required=True)
@pass_config
def patch_create(config, name):
    """
    creates the patch
    """
    config.patch_dir.mkdir(exist_ok=True, parents=True)
    PATCHFILE = config.patch_dir / __safe_filename(name) + ".patch"

    diff = _patch_get_diff(config)
    if diff:
        with open(PATCHFILE, 'w') as f:
            f.write(diff)
    _patch_ungitify(config)
    click.echo("Created patch file: " + PATCHFILE)

@patch.command(name='apply')
@click.argument('filepath', required=True)
@pass_config
def patch_apply(config, filepath):
    """
    applies patch-file from parameter 2
    """
    _patch_gitify_on_need(config)
    subprocess.check_call(["git", "apply", filepath], cwd=config.odoo_local)

def _patch_list(absolute_path=True):
    filepaths = []
    filepaths += list(dirs['customs'].glob("**/*.patch"))
    filepaths += list((dirs['customs'] / 'common').glob("**/*.patch"))

    commit = __get_odoo_commit()

    click.echo("-------------------------------------------------------------------------------")
    click.echo(click.style("Odoo commit is {} - limiting patches to this version".format(commit), bold=True, fg="red"))
    click.echo("-------------------------------------------------------------------------------")

    # filter to commits
    def in_commit(path):
        match = re.findall(r'/[a-f,0-9]{40}/', str(path))
        for x in match:
            x = x[1:-1]
            if x != commit:
                return False

        return True

    filepaths = list(filter(in_commit, filepaths))

    # remove duplicate entries, because of symbolic links and so
    filepaths_hashes = {}
    for x in filepaths:
        m = hashlib.md5()
        with open(x, 'rb') as f:
            m.update(f.read())
        filepaths_hashes[m.hexdigest()] = x
    filepaths = sorted(filepaths_hashes.values())
    for filename in filepaths:
        if 'migration' in filename.relative_to(odoo_config.customs_dir()).parts:
            continue
        if not absolute_path:
            filename = filename.relative_to(dirs['customs'])
        yield filename

@patch.command(name='list')
def patch_list():
    """
    lists all patches
    """
    for filename in _patch_list(absolute_path=False):
        click.echo(filename)

@patch.command(name='apply-all')
@pass_config
@click.pass_context
def apply_all(ctx, config):
    """
    applies all patches; no git repo after-wards
    """
    ctx.invoke(patch_reset)
    _patch_default_patches(config)
    for filepath in _patch_list():
        click.echo("Applying patch {}".format(filepath.relative_to(odoo_config.customs_dir())))
        ctx.invoke(patch_apply, filepath=filepath)
    _patch_ungitify(config)
    click.echo("Successfully applied all patches and cleaned .git directory.")

@patch.command(name='reset')
@pass_config
def patch_reset(config):
    """
    resets odoo to commit version
    """
    assert __get_odoo_commit()
    click.echo("Setting repo to commit {}".format(__get_odoo_commit()))
    subprocess.check_call([
        "git",
        "checkout",
        "-f",
        __get_odoo_commit()
    ], cwd=config.odoo_git)
    click.echo("Cleaning odoo repo...")
    subprocess.check_call([
        "git",
        "clean",
        "-xdff",
    ], cwd=config.odoo_git)
    click.echo("Rsyncing odoo-repo...")
    subprocess.check_call([
        "sudo",
        "rsync",
        str(config.odoo_git) + "/",
        str(config.odoo_local) + "/",
        '-rlDtp',
        '--delete-after',
    ], cwd=config.odoo_git)
    click.echo("CHOWN odoo-repo...")
    subprocess.check_call([
        'sudo',
        'chown',
        '-R',
        str(config.owner_uid or 0),
        config.odoo_local,
    ], cwd=config.odoo_git)
    subprocess.check_call([
        'sudo',
        'chmod',
        'a+w',
        "-R",
        config.odoo_local,
    ], cwd=config.odoo_git)
    click.echo("Cutting off local git")
    subprocess.check_call([
        'rm',
        '-Rf',
        config.sub_git,
    ], cwd=config.odoo_local)

def _patch_gitify(config):
    if config.odoo_local_dir not in __read_file(config.ignore_file):
        __append_line(config.ignore_file, config.odoo_local_dir)

    if config.sub_git.exists():
        shutil.rmtree(config.sub_git)

    click.echo("Making local git repo... in {}".format(config.odoo_local))
    subprocess.check_call(["git", "init", "."], cwd=config.odoo_local)
    click.echo("Adding files...")
    subprocess.check_call(["git", "add", "."], cwd=config.odoo_local)
    subprocess.check_call(["git", "config", "user.email", os.getenv("USER")], cwd=config.odoo_local)
    subprocess.check_call(["git", "commit", "-qam", "initial"], cwd=config.odoo_local)
    click.echo("Done")

def _patch_gitify_on_need(config):
    if not config.sub_git.exists():
        _patch_gitify(config)

def _patch_rmerror(function, path, excinfo):
    if excinfo[0] == OSError and excinfo[1].errno == 2:
        click.echo('Could not delete %s\n%s' % (path, excinfo[1].strerror))
    else:
        raise excinfo[1]

def _patch_ungitify(config):
    if config.sub_git.exists():
        shutil.rmtree(config.sub_git, True, onerror=_patch_rmerror)

def _patch_default_patches(config):
    click.echo("Applying default patches")
    click.echo("-remove module install notfications")

    from module_tools.module_tools import remove_module_install_notifications
    remove_module_install_notifications(dirs['customs'])
    click.echo("Apply default patches DONE")

def _patch_get_diff(config):
    subprocess.check_call(["git", "add", "--intent-to-add", "."], cwd=config.odoo_local)
    diff = subprocess.checkc_output(["git", "diff", "--binary"], cwd=config.odoo_local)
    return diff
