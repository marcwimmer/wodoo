#!/usr/bin/env python3
# is called by watchman to start unison sync
import sys
import os
import subprocess
from copy import deepcopy
args = sys.argv[1:]
if not args:
    args = [""]
cmd = [
    "unison",
    "unison_odoo_src.prf",
]
for filename in args:
    _cmd = deepcopy(cmd)
    if filename:
        print("Fast sync of changed path: {}".format(filename))
        _cmd += [
            "-path",
            str(filename),
        ]
    # sync changed files
    subprocess.call(_cmd)

# sync all
subprocess.call(cmd)
