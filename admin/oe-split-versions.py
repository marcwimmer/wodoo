#!/usr/bin/python
# splits the module content into subdirectories of versions

import os
import re
import sys
import shutil
from consts import MANIFESTS
from consts import VERSIONS
from shutil import copytree

def is_version(text):
    return bool([x for x in re.findall(r'[\d\.]*', text) if len(x) > 1])


parent_path = os.path.abspath(os.path.join(os.getcwd(), '..'))
if is_version(os.path.basename(parent_path)):
    print "Parent path is already a version!"
    sys.exit(-1)

files_in_dir = [x for x in os.listdir(os.getcwd()) if x not in ['.git', '.gitignore'] and not is_version(x)]


def write_version(path, v):
    with open(os.path.join(path, '.ln'), "w") as f:
        f.write("{'maximum_version': %s, 'minimum_version': %s}" % (v, v))


for v in VERSIONS:
    subdir = os.path.join(os.getcwd(), v)
    if not os.path.isdir(subdir):
        os.makedirs(subdir)
    else:
        print "Splitting already done"
        sys.exit(-1)

    for filedir in files_in_dir:
        if os.path.isdir(filedir):
            copytree(filedir, os.path.join(subdir, filedir))
        else:
            shutil.copy(filedir, os.path.join(subdir, filedir))

        # wenn einfaches untermodul, dann ln direkt anpassen
        if any(x in files_in_dir for x in MANIFESTS):
            write_version(subdir, v)
        else:
            # ansonsten von allen unteren modulen die versionsnummer anpassen
            for path, dirs, files in os.walk(subdir):
                for f in files:
                    if f == '.ln':
                        write_version(path, v)
for fd in files_in_dir:
    if os.path.isdir(fd):
        shutil.rmtree(fd)
    else:
        os.unlink(fd)
