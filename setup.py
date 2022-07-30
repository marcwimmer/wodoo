#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import sys
from glob import glob
from shutil import rmtree
from pathlib import Path
from setuptools.config import read_configuration

from setuptools import find_packages, setup, Command
from setuptools.command.install import install

import inspect
import os

current_dir = Path(
    os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
)
setup_cfg = read_configuration("setup.cfg")
metadata = setup_cfg["metadata"]
NAME = metadata["name"]

REQUIRED = list(
    filter(
        bool,
        (current_dir / metadata["name"] / "requirements.txt").read_text().split("\n"),
    )
)

here = os.path.abspath(os.path.dirname(__file__))

try:
    with io.open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = "\n" + f.read()
except FileNotFoundError:
    long_description = metadata["DESCRIPTION"]

# Load the package's __version__.py module as a dictionary.
about = {}
if not metadata["version"]:
    project_slug = metadata["name"].lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, "__version__.py")) as f:
        exec(f.read(), about)
else:
    about["__version__"] = metadata["version"]


def get_data_files():
    data_files = []
    for i, file in enumerate((current_dir / metadata["name"]).rglob("*")):
        if not file.is_file():
            continue
        if any(file.name.endswith(x) for x in [".pyc", ".py"]):
            continue
        if file.name.startswith("."):
            continue
        path = str(file.relative_to(current_dir))
        data_files.append((str(path), [path]))

    return data_files


# Where the magic happens:
setup(
    version=about["__version__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    # If your package is a single module, use this instead of 'packages':
    # py_modules=['prlsnapshotter'],
    data_files=get_data_files(),
    install_requires=REQUIRED,
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    include_package_data=True,
    cmdclass={
    },
)
