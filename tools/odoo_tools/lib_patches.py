import arrow
from pathlib import Path
import sys
import re
import subprocess
import shutil
import hashlib
import os
import tempfile
import click
import inquirer
from .odoo_config import MANIFEST
from .tools import __assert_file_exists
from .tools import __safe_filename
from .tools import __read_file
from .tools import __write_file
from .tools import __append_line
from .tools import __get_odoo_commit
from .tools import __remove_tree
from .tools import sync_folder
from .tools import _is_dirty
from . import odoo_config
from . import cli, pass_config, dirs, files
from .lib_clickhelpers import AliasedGroup

DATEFORMAT = "%Y-%m-%d"

def _get_odoo_github_disk_path():
    url = Path(os.environ['ODOO_REPO']).absolute()
    if not Path(url).exists() and not Path(url).absolute().is_dir():
        click.echo("Requires odoo on from github cloned to disk.")
        sys.exit(-1)
    return url

def _get_all_OCA_modules():
    yield from MANIFEST()['OCA']

def _prepare_OCA_source_folder(config, pull=False):
    """
    Fetches all OCA modules into single directory.
    """
    p = config.oca_src_dir
    p.mkdir(exist_ok=True, parents=True)

    for OCA in _get_all_OCA_modules():
        click.echo("Preparing {}".format(OCA))
        url = 'https://github.com/OCA/{}.git'.format(OCA)
        sub_path = p / OCA
        if not sub_path.exists():
            subprocess.check_call([
                "git",
                "clone",
                url,
                sub_path.name
            ], cwd=sub_path.parent)
        subprocess.check_call([
            "git",
            "clean",
            "-xdff"
        ], cwd=sub_path)
        subprocess.check_call([
            "git",
            "checkout",
            "-f",
            str(odoo_config.current_version()),
        ], cwd=sub_path)

        if pull:
            subprocess.check_call([
                "git",
                "pull",
            ], cwd=sub_path)

def _get_all_intermediate_repos(config):
    dirs = \
        [config.odoo_dir.absolute()] + \
        list(config.oca_dir.absolute() / oca for oca in _get_all_OCA_modules())
    return dirs

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
    config.odoo_dir = dirs['customs'] / 'odoo'
    config.ignore_file = dirs['customs'] / '.gitignore'
    config.odoo_git = _get_odoo_github_disk_path()
    config.patch_dir = M.patch_dir
    config.oca_dir = dirs['customs'] / 'addons_OCA'
    config.oca_src_dir = Path(os.environ['ODOO_OCA_FOLDER'])
    odoo_dir = dirs['customs'] / 'odoo'
    __assert_file_exists(odoo_dir, isdir=True)

    config.patch_dir.mkdir(exist_ok=True, parents=True)

@patch.command(name='prepare')
@pass_config
@click.pass_context
def patch_prepare(ctx, config):
    """
    makes git repo at odoo and applies default patches like remove install notifications
    """
    from git import Repo
    ctx.invoke(patch_reset)
    _patch_gitify(config)
    _patch_default_patches(config)

    for dir in _get_all_intermediate_repos(config):
        subprocess.check_call(["git", "add", "."], cwd=dir)
        subprocess.call(["git", "commit", "-qam", "removed install notifications"], cwd=dir)

    patches = [x for x in _patch_list(config)]
    for filepath in patches:
        _patch_apply(config, filepath)
    for dir in _get_all_intermediate_repos(config):
        subprocess.check_call(["git", "add", "."], cwd=dir)
        repo = Repo(dir)
        if _is_dirty(repo, True):
            subprocess.check_call(["git", "commit", "-qam", "applied all current patches"], cwd=dir)
    click.echo("You can now do changes; use odoo patch preview to display your changes.")

@patch.command(name='preview')
@pass_config
def patch_preview(config):
    """
    shows what is patched
    """
    for dir, diff in _patch_get_diff(config):
        click.secho("\n{}\n===============================".format(dir), bold=True, fg='yellow')
        filename = Path(tempfile.mktemp(suffix='.'))
        filename.write_bytes(diff)
        os.system('cat "{}" | colordiff'.format(filename))
        filename.unlink()

@patch.command(name='create')
@click.argument('name', required=True)
@pass_config
def patch_create(config, name):
    """
    creates the patch
    """
    config.patch_dir.mkdir(exist_ok=True, parents=True)
    name = __safe_filename(name) + ".patch"

    for rel_dir, diff in _patch_get_diff(config):
        dir = config.patch_dir
        dir.mkdir(parents=True, exist_ok=True)
        PATCHFILE = dir / name
        diff = diff.decode("utf-8")
        diff = """odoo-path\nrelative_path:{}\n
""".format(rel_dir) + diff
        PATCHFILE.write_text(diff)
        click.echo("Created patch file: {}".format(PATCHFILE))

    _patch_ungitify(config)

def _patch_apply(config, filepath):
    """
    applies patch-file from parameter 2
    """
    filepath = Path(filepath).absolute()
    dir = dirs['customs'] / filepath.parent.relative_to(config.patch_dir)
    patch_content = filepath.read_text().split("\n")
    if patch_content[0] != 'odoo-patch':
        click.secho("Requires odoo-patch in first line; next line must contain relative_path")
        sys.exit(-1)
    relative_path = patch_content[1].replace("relative_path:", "").strip("")
    with filepath.open() as f:
        subprocess.check_call(["patch", "-p1"], cwd=dir / relative_path, stdin=f)

def _patch_list(config, absolute_path=True):

    filepaths = [x.absolute() for x in config.patch_dir.glob("**/*.patch")]

    # filter to commits
    def in_commit(path):
        if 'migration' in path.parts:
            return False
        return True

    filepaths = list(set(filter(in_commit, filepaths)))

    for filename in filepaths:
        if not absolute_path:
            filename = filename.relative_to(dirs['customs'])
        yield filename

@patch.command(name="integrate-patch")
@pass_config
def intergate_patch(config):
    """
    Symlinks patch from modules into the ./patches dir
    """
    patches_dir = dirs['customs'] / 'patches'
    existing_patches = [x.resolve().absolute() for x in patches_dir.glob("**/*.patch")]
    check = [x.absolute() for x in dirs['customs'].glob("**/*.patch") if not x.is_symlink() and x.parent != patches_dir and x.absolute() not in existing_patches]

    # filter out special patches
    check = [x for x in check if not any(y in ['migration', 'migrations'] for y in x.parts)]
    if not check:
        click.secho("Not any more patches found to add.")
        sys.exit(-1)
    questions = [
        inquirer.Checkbox(
            'patches',
            message="Add which patches?",
            choices=check,
        )
    ]
    answers = inquirer.prompt(questions)
    for patch in answers['patches']:
        file_in_patches_dir = (patches_dir / patch.name)
        file_in_patches_dir.symlink_to(patch.relative_to(dirs['customs']) / patch)


@patch.command(name='list')
@pass_config
def patch_list(config):
    """
    lists all patches
    """
    for filename in _patch_list(config, absolute_path=False):
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
    customs_dir = odoo_config.customs_dir()
    for filepath in _patch_list(config):
        click.secho("Applying patch {}".format(filepath.relative_to(customs_dir)), fg='green')
        _patch_apply(config, filepath)
    _patch_ungitify(config)
    click.echo("Successfully applied all patches and cleaned .git directory.")

@patch.command(name='reset')
@pass_config
def patch_reset(config):
    """
    resets odoo to commit version
    resets all OCA modules to current branch
    """
    _prepare_OCA_source_folder(config)
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
    if (config.odoo_dir / '.git').exists():
        __remove_tree(config.odoo_dir / '.git')
    click.echo("Rsyncing odoo-repo...")
    sync_folder(config.odoo_git, config.odoo_dir, excludes=['.git'])
    click.echo("CHOWN odoo-repo...")
    if config.owner_uid:
        subprocess.check_call([
            'chown',
            '-R',
            str(config.owner_uid or 0),
            config.odoo_dir,
        ], cwd=config.odoo_git)
    subprocess.check_call([
        'chmod',
        "-R",
        'a+w',
        config.odoo_dir,
    ], cwd=config.odoo_git)
    click.echo("Resetting OCA Modules to current version")
    for oca in _get_all_OCA_modules():
        sync_folder(
            config.oca_src_dir / oca,
            config.oca_dir / oca,
            excludes=['.git'],
        )
        gitdir = config.oca_dir / oca / '.git'
        if gitdir.exists():
            __remove_tree(gitdir)


def _patch_gitify(config):
    def _gitify_folder(dir):

        git_folder = dir / '.git'
        if git_folder.exists():
            __remove_tree(git_folder)

        click.echo("Making local git repo... in {}".format(dir))
        subprocess.check_call(["git", "init", "."], cwd=dir)
        click.echo("Adding files...")
        subprocess.check_call(["git", "add", "."], cwd=dir)
        subprocess.check_call(["git", "config", "user.email", os.getenv("USER")], cwd=dir)
        subprocess.check_call(["git", "commit", "-qam", "initial"], cwd=dir)

    _gitify_folder(config.odoo_dir)
    for oca in _get_all_OCA_modules():
        _gitify_folder(config.oca_dir / oca)

def _patch_gitify_on_need(config):
    if any(not (dir / '.git').exists() for dir in _get_all_intermediate_repos(config)):
        _patch_gitify(config)

def _patch_rmerror(function, path, excinfo):
    if excinfo[0] == OSError and excinfo[1].errno == 2:
        click.echo('Could not delete %s\n%s' % (path, excinfo[1].strerror))
    else:
        raise excinfo[1]

def _patch_ungitify(config):
    dirs = _get_all_intermediate_repos(config)
    for dir in dirs:
        git_dir = dir / '.git'
        if git_dir.exists():
            __remove_tree(git_dir)

def _patch_default_patches(config):
    click.echo("Applying default patches")
    click.echo("-remove module install notfications")

    from .module_tools import remove_module_install_notifications
    remove_module_install_notifications(dirs['customs'])
    click.echo("Apply default patches DONE")

def _patch_get_diff(config):
    from git import Repo

    def _get_diff_of_repo(dir):
        diff = subprocess.check_output(["git", "diff", "--binary"], cwd=dir)
        return diff

    result = []
    for rep in _get_all_intermediate_repos(config):
        subprocess.check_call(["git", "add", "--intent-to-add", "."], cwd=rep)
        diff = _get_diff_of_repo(rep)
        if diff:
            result.append((
                rep.relative_to(dirs['customs']),
                diff,
            ))

    return result
