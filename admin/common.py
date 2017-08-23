import os
import pdb
import json
import traceback
import sys
import inspect
import subprocess
import threading
dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))) # script directory


CUSTOMS = os.getenv("CUSTOMS", threading.currentThread().CUSTOMS)
if not CUSTOMS:
    raise Exception("common.py requires environment variable CUSTOMS")

# global variables
version = False

root_path = os.path.normpath("%s/.." % dir)

# if there is /opt/odoo/active_customs then this wins
active_customs_path = os.path.join(root_path, 'active_customs')

if os.path.isdir(active_customs_path) or os.path.islink(active_customs_path):
    customs_path = active_customs_path
else:
    customs_path = os.path.join(root_path, 'customs', CUSTOMS)

# search for addon paths
addons_paths = []
folders = subprocess.check_output("find " + unicode(os.path.join(customs_path, "odoo")) + "/ -name addons -type d| grep -v .git |grep -v test", shell=True)
addons_paths += [x for x in folders.split("\n") if 'test' not in x and x.endswith("/addons") and 'odoo/odoo' not in x]

version_file = os.path.join(customs_path, ".version")
if not os.path.exists(version_file):
    raise Exception(u".version file required which contains 7.0 or 8.0 or so: {}".format(version_file))

with open(version_file) as f:
    content = f.read()
    try:
        version = float(content)
    except:
        try:
            version = dict(content)['version']
        except Exception:
            msg = traceback.format_exc()
            raise Exception(u"Error reading version from {}, {}".format(version_file, msg))

if len(sys.argv) > 1 and sys.argv[1] == '--output-addonspaths':
    print ','.join(addons_paths)
