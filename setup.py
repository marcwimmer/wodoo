#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import shutil
import io
import os
import sys
import json
import requests
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

class UninstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        raise Exception('stop1')
class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        self.setup_click_autocompletion()
        self.download_artefacts()

    def download_artefacts(self):
        path = Path("artefacts")
        if not path.exists():
            return
        artefacts = json.loads(path.read_text())
        base_path = Path(self.install_lib) / metadata['name']
        for path, files in artefacts.items():
            path = base_path / path
            path.mkdir(exist_ok=True, parents=True)
            for file in files:
                self.download_file_and_move(
                    file,
                    path
                )

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

        def setup_for_shell_generic(shell, shell_call):
            path = Path(f"/etc/{shell}_completion.d")
            completion = (Path("completions") / f"odoo.{shell}").read_bytes()
            if path.exists():
                if os.access(path, os.W_OK):
                    (path / shell_call).write_bytes(completion)
                    return

            if not (path / shell_call).exists():
                rc = Path(os.path.expanduser("~")) / f'.{shell}rc'
                if not rc.exists():
                    return
                complete_file = rc.parent / f'.{shell_call}-completion.sh'
                complete_file.write_bytes(completion)
                if complete_file.name not in rc.read_text():
                    content = rc.read_text()
                    content += '\nsource ~/' + complete_file.name
                    rc.write_text(content)

        for console_script in setup_cfg['options']['entry_points']['console_scripts']:
            shell_call = console_script.split("=")[0].strip()
            for console in ['zsh', 'bash', 'fish']:
                setup_for_shell_generic(console, shell_call)


def get_data_files():
    data_files = []
    for i, file in enumerate((current_dir / metadata['name']).rglob("*")):
        if not file.is_file():
            continue
        if any(file.name.endswith(x) for x in ['.pyc', '.py']):
            continue
        if file.name.startswith('.'):
            continue
        if file.name in ['requirements.txt']:
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
    extras_require=EXTRAS,
    include_package_data=True,
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
        'install': InstallCommand,
    },
)
