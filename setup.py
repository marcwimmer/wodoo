#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import io
import os
import sys
from glob import glob
from shutil import rmtree
from pathlib import Path
from setuptools.config import read_configuration

from setuptools import find_packages, setup, Command
from setuptools.command.install import install
import subprocess

import inspect
import os

# HACK to ignore wheel building from pip and just to source distribution
if 'bdist_wheel' in sys.argv:
    sys.exit(0)

current_dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
setup_cfg = read_configuration("setup.cfg")
metadata = setup_cfg['metadata']
NAME = metadata['name']

REQUIRED = list(filter(bool, (current_dir / metadata['name'] / 'requirements.txt').read_text().split("\n")))

here = os.path.abspath(os.path.dirname(__file__))

try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = metadata['DESCRIPTION']

# Load the package's __version__.py module as a dictionary.
about = {}
if not metadata['version']:
    project_slug = metadata['name'].lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = metadata['version']


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def clear_builds(self):
        for path in ['dist', 'build', NAME.replace("-", "_") + ".egg-info"]:
            try:
                self.status(f'Removing previous builds from {path}')
                rmtree(os.path.join(here, path))
            except OSError:
                pass

    def run(self):
        self.clear_builds()

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        self.clear_builds()

        sys.exit()

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        self.setup_click_autocompletion()

    def setup_click_autocompletion(self):
        for console_script in setup_cfg['options']['entry_points']['console_scripts']:
            console_call = console_script.split("=")[0].strip()

            # if click completion helper is fresh installed and not available now
            subprocess.run(["pip3", "install", "click-completion-helper"])
            subprocess.run([
                "click-completion-helper",
                "setup",
                console_call,
            ])


def get_data_files():
    data_files = []
    for i, file in enumerate((current_dir / metadata['name']).rglob("*")):
        if not file.is_file():
            continue
        if any(file.name.endswith(x) for x in ['.pyc', '.py']):
            continue
        if file.name.startswith('.'):
            continue
        path = str(file.relative_to(current_dir))
        data_files.append((str(path), [path]))

    return data_files

# Where the magic happens:
setup(
        version=about['__version__'],
        long_description=long_description,
        long_description_content_type='text/markdown',
        # If your package is a single module, use this instead of 'packages':
        #py_modules=['prlsnapshotter'],
        data_files=get_data_files(),
        install_requires=REQUIRED,
        packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
        include_package_data = True,
        cmdclass={
            'upload': UploadCommand,
            'install': InstallCommand,
        },
)