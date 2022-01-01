#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import io
import os
import sys
from shutil import rmtree
from pathlib import Path

from setuptools import find_packages, setup, Command
from setuptools.command.install import install
from subprocess import check_call, check_output



# Package meta-data.
NAME = 'wodoo'
SHELL_CALL = "odoo"
DESCRIPTION = 'Odoo Framework.'
URL = 'https://git.itewimmer.de/odoo/framework'
EMAIL = 'marc@itewimmer.de'
AUTHOR = 'Marc-Christian Wimmer'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = '0.1.0'

# What packages are required for this module to be executed?
REQUIRED = [
    "pyyaml",
    "arrow>=0.14.6",
    "Click>=8.0.1",
    "click-default-group>=1.2.1",
    "pathlib>=1.0.1",
    "inquirer>=2.6.3",
    "retrying>=1.3.3",
    "humanize>=0.5.1",
    "passlib>=1.7.1",
    "tabulate>=0.8.3",
    "psycopg2-binary>=2.8.3",
    "requests>=2.20.1",
    "lxml>=4.4.1",
    "psutil>=5.6.3",
    "GitPython>=3.1.11",
    "docker-compose==1.27.3",
    "iscompatible",
    "buttervolume>=3.7",
    "pudb",
    "gimera",
]


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
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


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

def setup_click_autocompletion():

    def setup_for_shell_generic(shell):
        path = Path(f"/etc/{shell}_completion.d")
        technical_name = SHELL_CALL.upper().replace("-", "_")
        completion = check_output(["/usr/local/bin/" + SHELL_CALL], env={
            f"_{technical_name}_COMPLETE": f"{shell}_source"
        })
        if path.exists():
            if os.access(path, os.W_OK):
                (path / SHELL_CALL).write_bytes(completion)
                return

        if not (path / NAME).exists():
            rc = Path(os.path.expanduser("~")) / f'.{shell}rc'
            if not rc.exists():
                return
            complete_file = rc.parent / f'.{SHELL_CALL}-completion.sh'
            complete_file.write_bytes(completion)
            if complete_file.name not in rc.read_text():
                content = rc.read_text()
                content += '\nsource ~/' + complete_file.name
                rc.write_text(content)

    setup_for_shell_generic('zsh')
    setup_for_shell_generic('bash')
    setup_for_shell_generic('fish')

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        setup_click_autocompletion()

# Where the magic happens:
setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    # If your package is a single module, use this instead of 'packages':
    #py_modules=['prlsnapshotter'],

    entry_points={
        'console_scripts': [SHELL_CALL + '=framework:cli'],
    },
    data_files=[
    ],
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    license='MIT',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
        'install': InstallCommand,
    },
)
