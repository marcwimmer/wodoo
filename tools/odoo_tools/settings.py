import os
import click
import tempfile
from pathlib import Path
from contextlib import contextmanager
from .odoo_config import MANIFEST

def _get_settings_files(config, customs):
    """
    Returns list of paths or files
    """
    from . import odoo_config
    customs_dir = config.WORKING_DIR

    if customs_dir:
        yield customs_dir / 'settings'
    yield Path('/etc/odoo/settings')
    if customs: # catch what goes; if no customs given, then perhaps first init run done or so
        yield Path(f'/etc/odoo/{config.CUSTOMS}/settings')
    if config.PROJECT_NAME:
        yield Path(f'/etc/odoo/{config.PROJECT_NAME}/settings')
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

def _export_settings(config, customs, forced_values):
    from . import odoo_config
    from .myconfigparser import MyConfigParser

    if not config.files['settings'].exists():
        raise Exception("Please call ./odoo compose <CUSTOMS> initially.")

    setting_files = _collect_settings_files(config, customs)
    _make_settings_file(config.files['settings'], setting_files)
    # constants
    config = MyConfigParser(config.files['settings'])
    if 'OWNER_UID' not in config.keys():
        config['OWNER_UID'] = str(os.getuid())
    # take server wide modules from manifest
    m = MANIFEST()
    config['SERVER_WIDE_MODULES'] = ','.join(m['server-wide-modules'])

    # forced values:
    for k, v in forced_values.items():
        config[k] = v

    config.write()

def _collect_settings_files(config, customs, quiet=False):
    _files = []

    if config.dirs:
        _files.append(config.dirs['odoo_home'] / 'images/defaults')
        # optimize
        for filename in config.dirs['images'].glob("**/default.settings"):
            _files.append(config.dirs['images'] / filename)
    if 'settings_auto' in _files:
        _files.append(config.files['settings_auto'])

    for dir in filter(lambda x: x.exists(), _get_settings_files(config, customs)):
        if not quiet:
            click.secho("Searching for settings in: {}".format(dir), fg='cyan')
        if dir.is_file():
            _files.append(dir)
        elif dir.is_dir():
            for file in dir.glob("settings*"):
                if file.is_dir():
                    continue
                _files.append(file)

    if config.files:
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
        if 'images' not in Path(file).parts:
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
