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
from subprocess import check_call, check_output

import inspect
import os
from pathlib import Path
current_dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
setup_cfg = read_configuration("setup.cfg")
metadata = setup_cfg['metadata']


# Package meta-data.
# What packages are required for this module to be executed?
REQUIRED = list(filter(bool, (current_dir / metadata['name'] / 'requirements.txt').read_text().split("\n")))

# What packages are optional?
EXTRAS = {
    # 'fancy feature': ['django'],
}

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
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

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)

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

def _post_install(setup):
    def _post_actions():
        Path("/tmp/post").write_text("HI")
    _post_actions()
    return setup

# Where the magic happens:
setup = _post_install(
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
        extras_require=EXTRAS,
        # $ setup.py publish support.
        cmdclass={
            'upload': UploadCommand,
            'install': InstallCommand,
        },
        classifiers=[
            # Trove classifiers
            # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: Implementation :: CPython',
            'Programming Language :: Python :: Implementation :: PyPy'
        ]
    )

)