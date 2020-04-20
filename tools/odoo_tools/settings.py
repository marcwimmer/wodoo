import os
import click
import tempfile
from pathlib import Path
from contextlib import contextmanager
from .odoo_config import MANIFEST

def _get_settings_directories(customs):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    from . import dirs
    customs_dir = odoo_config.customs_dir()
    project_name = os.environ["PROJECT_NAME"]
    yield customs_dir / 'settings'
    yield Path('/etc/odoo/settings')
    yield Path('/etc/odoo/{}/settings'.format(customs))
    yield Path('/etc/odoo/{}/settings'.format(project_name))
    yield Path('{}/.odoo'.format(os.environ['HOME']))

@contextmanager
def _get_settings(dirs, files, customs):
    from .myconfigparser import MyConfigParser  # NOQA
    files = _collect_settings_files(dirs=dirs, files=files, customs=None, quiet=True)
    filename = tempfile.mktemp(suffix='.')
    _make_settings_file(filename, files)
    c = MyConfigParser(filename)
    try:
        yield c
    finally:
        Path(filename).unlink()

def _export_settings(customs):
    from . import files
    from . import dirs
    from . import odoo_config
    from . import MyConfigParser

    if not files['settings'].exists():
        raise Exception("Please call ./odoo compose <CUSTOMS> initially.")

    setting_files = _collect_settings_files(dirs, files, customs)
    _make_settings_file(files['settings'], setting_files)
    # constants
    config = MyConfigParser(files['settings'])
    if 'OWNER_UID' not in config.keys():
        config['OWNER_UID'] = str(os.getuid())
    # take server wide modules from manifest
    m = MANIFEST()
    config['SERVER_WIDE_MODULES'] = ','.join(m['server-wide-modules'])

    config.write()

def _collect_settings_files(dirs, files, customs, quiet=False):
    _files = []
    if dirs:
        _files.append(dirs['odoo_home'] / 'images/defaults')
        # optimize
        for filename in dirs['images'].glob("**/default.settings"):
            _files.append(dirs['images'] / filename)
    if 'settings_auto' in _files:
        _files.append(files['settings_auto'])

    if customs:
        for dir in filter(lambda x: x.exists(), _get_settings_directories(customs)):
            click.secho("Searching for settings in: {}".format(dir), fg='cyan')
            if dir.is_dir() and 'settings' not in dir.name:
                continue
            if dir.is_file():
                _files.append(dir)
            elif dir.is_dir():
                for file in dir.glob("*"):
                    if file.is_dir():
                        continue
                    _files.append(file)

    _files.append(files['user_settings'])
    if files and 'project_settings' in files:
        if files['project_settings'].exists():
            _files.append(files['project_settings'])
        else:
            click.secho("No specific configuration file used: {}".format(files['project_settings']), fg='yellow')

    if not quiet:
        click.secho("Found following extra settings files:", fg='cyan')
    for file in _files:
        if not Path(file).exists():
            continue
        # click.secho(f"Using setting file: {file}", fg='blue')
        if 'images' not in Path(file).parts:
            if not quiet:
                click.echo(file)
                click.echo(file.read_text())

    return _files

def _make_settings_file(outfile, setting_files):
    """
    Puts all settings into one settings file
    """
    from . import MyConfigParser
    c = MyConfigParser(outfile)
    for file in setting_files:
        if not file:
            continue
        c2 = MyConfigParser(file)
        c.apply(c2)

    # expand variables
    for key in list(c.keys()):
        value = c[key]
        if "~" in value:
            c[key] = os.path.expanduser(value)

    c.write()
