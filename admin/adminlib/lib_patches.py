import re
import shutil
import hashlib
import os
import tempfile
import click
from .tools import __assert_file_exists
from .tools import __system
from .tools import __safe_filename
from .tools import __find_files
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __exists_odoo_commit
from .tools import __get_odoo_commit
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup


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
    config.odoo_local_dir = 'odoo'
    config.odoo_local = os.path.join(dirs['customs'], config.odoo_local_dir)
    config.ignore_file = os.path.join(dirs['customs'], '.gitignore')
    config.odoo_git = os.path.join(dirs['odoo_home'], 'repos/odoo')
    config.patch_dir = os.path.join(dirs['customs'], 'common/patches', __get_odoo_commit())
    config.sub_git = os.path.join(config.odoo_local, '.git')
    odoo_dir = os.path.join(dirs['customs'], 'odoo')
    __assert_file_exists(odoo_dir, isdir=True)

    if not os.path.exists(config.patch_dir):
        os.mkdir(config.patch_dir)

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

    __system(["git", "add", "."], cwd=config.odoo_local)
    try:
        __system(["git", "commit", "-qam", "removed install notifications"], cwd=config.odoo_local)
    except Exception:
        click.echo("Perhaps no install notifications")
    patches = [x for x in _patch_list(config)]
    for filepath in patches:
        ctx.invoke(patch_apply, filepath=filepath)
    __system(["git", "add", "."], cwd=config.odoo_local)
    if patches:
        __system(["git", "commit", "-qam", "applied all current patches"], cwd=config.odoo_local)
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
    if not os.path.exists(config.patch_dir):
        os.makedirs(config.patch_dir)
    PATCHFILE = os.path.join(config.patch_dir, __safe_filename(name) + ".patch")

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
    __system(["git", "apply", filepath], cwd=config.odoo_local)

def _patch_list(absolute_path=True):
    filepaths = []
    filepaths += __find_files(dirs['customs'], "-name", "*.patch")
    filepaths += __find_files(os.path.join(dirs['customs'], 'common'), "-name", "*.patch")

    commit = __get_odoo_commit()

    click.echo("-------------------------------------------------------------------------------")
    click.echo(click.style("Odoo commit is {} - limiting patches to this version".format(commit), bold=True, fg="red"))
    click.echo("-------------------------------------------------------------------------------")

    # filter to commits
    def in_commit(path):
        match = re.findall(r'/[a-f,0-9]{40}/', path)
        for x in match:
            x = x[1:-1]
            if x != commit:
                return False

        return True

    filepaths = filter(in_commit, filepaths)

    # remove duplicate entries, because of symbolic links and so
    filepaths_hashes = {}
    for x in filepaths:
        m = hashlib.md5()
        with open(x, 'rb') as f:
            m.update(f.read())
        filepaths_hashes[m.hexdigest()] = x
    filepaths = sorted(filepaths_hashes.values())
    for filename in filepaths:
        if '/migration/' in filename:
            continue
        if not absolute_path:
            filename = os.path.relpath(filename, dirs['customs'])
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
        click.echo("Applying patch " + filepath)
        ctx.invoke(patch_apply, filepath=filepath)
    _patch_ungitify(config)
    click.echo("Successfully applied all patches and cleaned .git directory.")

@patch.command(name='reset')
@pass_config
def patch_reset(config):
    """
    resets odoo to commit version
    """
    __exists_odoo_commit()
    click.echo("Setting repo to commit {}".format(__get_odoo_commit()))
    __system([
        "git",
        "checkout",
        "-f",
        __get_odoo_commit()
    ], cwd=config.odoo_git)
    click.echo("Cleaning odoo repo...")
    __system([
        "git",
        "clean",
        "-xdff",
    ], cwd=config.odoo_git)
    click.echo("Rsyncing odoo-repo...")
    __system([
        "sudo",
        "rsync",
        config.odoo_git + "/",
        config.odoo_local + "/",
        '-rlDtp',
        '--delete-after',
    ], cwd=config.odoo_git, suppress_out=False)
    click.echo("CHOWN odoo-repo...")
    __system([
        'sudo',
        'chown',
        '-R',
        str(config.owner_uid or 0),
        config.odoo_local,
    ], cwd=config.odoo_git)
    __system([
        'sudo',
        'chmod',
        'a+w',
        "-R",
        config.odoo_local,
    ], cwd=config.odoo_git)
    click.echo("Cutting off local git")
    __system([
        'rm',
        '-Rf',
        config.sub_git,
    ], cwd=config.odoo_local)

def _patch_gitify(config):
    if config.odoo_local_dir not in __read_file(config.ignore_file):
        __append_line(config.ignore_file, config.odoo_local_dir)

    if os.path.exists(config.sub_git):
        shutil.rmtree(config.sub_git)

    click.echo("Making local git repo... in {}".format(config.odoo_local))
    __system(["git", "init", "."], cwd=config.odoo_local)
    click.echo("Adding files...")
    __system(["git", "add", "."], cwd=config.odoo_local)
    __system(["git", "config", "user.email", os.getenv("USER")], cwd=config.odoo_local)
    __system(["git", "commit", "-qam", "initial"], cwd=config.odoo_local)
    click.echo("Done")

def _patch_gitify_on_need(config):
    if not os.path.exists(config.sub_git):
        _patch_gitify(config)

def _patch_rmerror(function, path, excinfo):
    if excinfo[0] == OSError and excinfo[1].errno == 2:
        click.echo('Could not delete %s\n%s' % (path, excinfo[1].strerror))
    else:
        raise excinfo[1]

def _patch_ungitify(config):
    if os.path.exists(config.sub_git):
        shutil.rmtree(config.sub_git, True, onerror=_patch_rmerror)

def _patch_default_patches(config):
    click.echo("Applying default patches")
    click.echo("-remove module install notfications")

    from module_tools.module_tools import remove_module_install_notifications
    remove_module_install_notifications(dirs['customs'])
    click.echo("Apply default patches DONE")

def _patch_get_diff(config):
    __system(["git", "add", "--intent-to-add", "."], cwd=config.odoo_local)
    filename = tempfile.mktemp(suffix='.diff')
    wkd = os.getcwd()
    os.chdir(config.odoo_local)
    os.system('git diff --binary > \'{}\''.format(filename))
    os.chdir(wkd)
    with open(filename, 'r') as f:
        diff = f.read()
    #diff = __system(["git", "diff", "--binary"], cwd=config.odoo_local, suppress_out=False) # Big fucking bug: terminates incompleted
    return diff
