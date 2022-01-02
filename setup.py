#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import shutil
import io
import os
import sys
import requests
from glob import glob
from shutil import rmtree
from pathlib import Path

from setuptools import find_packages, setup, Command
from setuptools.command.install import install
from subprocess import check_call, check_output

import inspect
import os
from pathlib import Path
current_dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))


# Package meta-data.
NAME = 'wodoo'
SHELL_CALL = "odoo"
DESCRIPTION = 'Odoo Framework'
URL = 'https://git.itewimmer.de/odoo/framework'
EMAIL = 'marc@itewimmer.de'
AUTHOR = 'Marc-Christian Wimmer'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = '0.1.0'

# What packages are required for this module to be executed?
REQUIRED = list(filter(bool, (current_dir / 'wodoo' / 'requirements.txt').read_text().split("\n")))

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

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        self.setup_click_autocompletion()
        self.download_artefacts()

    def download_artefacts(self):
        path = Path(self.install_lib) / NAME
        path_robot_artefacts = path / 'images' / 'robot' / 'artefacts'
        path_robot_artefacts.mkdir(exist_ok=True)
        self.download_file_and_move('https://github.com/marcwimmer/chromedrivers/raw/2021-12/chromedriver_amd64.zip', path_robot_artefacts)
        self.download_file_and_move('https://github.com/marcwimmer/chromedrivers/raw/2021-12/googlechrome_amd64.deb', path_robot_artefacts)

    def download_file_and_move(self, url, dest_parent_path):
        file = self.download_file(url)
        file.rename(Path(dest_parent_path) / file.name)

    def download_file(self, url):
        print(f"Downloading {url}")
        local_filename = url.split('/')[-1]
        with requests.get(url, stream=True) as r:
            with open(local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        return Path(local_filename)

    def setup_click_autocompletion(self):

        def setup_for_shell_generic(shell):
            path = Path(f"/etc/{shell}_completion.d")
            technical_name = SHELL_CALL.upper().replace("-", "_")
            completion = check_output([str(Path(self.install_scripts) / SHELL_CALL)], env={
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



def get_data_files():
    data_files = []
    PREFIX = Path(sys.prefix) / 'local' / NAME
    for i, file in enumerate((current_dir / 'wodoo').rglob("*")):
        if not file.is_file():
            continue
        if any(file.name.endswith(x) for x in ['.pyc', '.py']):
            continue
        if file.name.startswith('.'):
            continue
        if file.name in ['requirements.txt']:
            continue
        path = str(file.relative_to(current_dir))
        data_files.append((str(PREFIX / path), [path]))

    return data_files


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
    data_files=get_data_files(),
    entry_points={
        'console_scripts': [SHELL_CALL + '=wodoo:cli'],
    },
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
