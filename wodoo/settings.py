import os
from pwd import getpwnam  
import sys
import click
import tempfile
from pathlib import Path
from contextlib import contextmanager
from .odoo_config import MANIFEST

def _get_settings_files(config):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    customs_dir = config.WORKING_DIR

    if customs_dir:
        yield customs_dir / 'settings'
    yield Path('/etc/odoo/settings')
    if config.project_name:
        yield Path(f'/etc/odoo/{config.project_name}/settings')
    yield customs_dir / '.odoo' / 'settings'
    yield Path(os.environ['HOME']) / '.odoo' / 'settings'
    yield customs_dir / '.odoo' / 'run' / 'settings'

@contextmanager
def _get_settings(config, customs, quiet=False):
    from .myconfigparser import MyConfigParser  # NOQA
    files = _collect_settings_files(config, customs=None, quiet=quiet)
    filename = tempfile.mktemp(suffix='.')
    _make_settings_file(filename, files)
    c = MyConfigParser(filename)
    try:
        yield c
    finally:
        Path(filename).unlink()

def _export_settings(config, forced_values):
    from . import odoo_config
    from .myconfigparser import MyConfigParser

    setting_files = _collect_settings_files(config)
    _make_settings_file(config.files['settings'], setting_files)
    # constants
    settings = MyConfigParser(config.files['settings'])
    if 'OWNER_UID' not in settings.keys():
        UID = int(os.getenv("SUDO_UID", os.getuid()))
        if not UID:
            # sometimes (in ansible) SUDO_UID is set to 0 but env USER exists
            if os.getenv("USER") and os.environ['USER'] != 'root':
                UID = getpwnam(os.environ['USER']).pw_uid
        settings['OWNER_UID'] = str(UID)

    # forced values:
    for k, v in forced_values.items():
        settings[k] = v

    settings['ODOO_IMAGES'] = config.dirs['images']

    settings.write()

def _collect_settings_files(config, quiet=False):
    _files = []

    if config.dirs:
        _files.append(config.dirs['odoo_home'] / 'defaults')
        # optimize
        for filename in config.dirs['images'].glob("**/default.settings"):
            _files.append(config.dirs['images'] / filename)
    if config.restrict['settings']:
        _files += config.restrict['settings']
    else:
        for dir in filter(lambda x: x.exists(), _get_settings_files(config)):
            if not quiet:
                click.secho("Searching for settings in: {}".format(dir), fg='cyan')
            if dir.is_file():
                _files.append(dir)
            elif dir.is_dir():
                for file in dir.glob("settings*"):
                    if file.is_dir():
                        continue
                    _files.append(file)

        # _files.append(files['user_settings'])
        if config.files and 'project_settings' in config.files:
            if config.files['project_settings'].exists():
                _files.append(config.files['project_settings'])
            else:
                click.secho("Hint: file for configuration can be used: {}".format(config.files['project_settings']), fg='magenta')

    if not quiet:
        click.secho("\n\nFound following extra settings files:\n", fg='cyan', bold=True)

    for file in _files:
        if not Path(file).exists():
            continue
        # click.secho(f"Using setting file: {file}", fg='blue')
        root = Path(sys.argv[0]).parent
        # if Path(file).relative_to(
        try:
            Path(file).relative_to(root)
        except ValueError:
            if not quiet:
                click.secho(f">>>>>>>>>>>>>>>>>>> {file} <<<<<<<<<<<<<<<<<", fg='cyan')
                click.secho(file.read_text())

    return _files

def _make_settings_file(outfile, setting_files):
    """
    Puts all settings into one settings file
    """
    from .myconfigparser import MyConfigParser
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
