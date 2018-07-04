#!/usr/bin/python
# executed in odoo container
import pipes
import sys
import os
import pickle
import subprocess
import base64
e, BRANCH, CMD, ADDONS_PATH, VERSION, MAKE_GIT_CLEAN = sys.argv
CMD = base64.b64decode(CMD)
CMD = pickle.loads(CMD)
CONFIG_FILE = "/home/odoo/config_migration"
OpenupgradeDir = os.path.join(os.environ["ODOO_REPOS_DIRECTORY"], "OpenUpgrade")
assert BRANCH and CMD and ADDONS_PATH and VERSION

def set_addons_path():
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    content = content.replace("__ADDONS_PATH__", ADDONS_PATH)
    with open(CONFIG_FILE, 'w') as f:
        f.write(content)
    subprocess.check_call(["/apply-env-to-config.sh"])
set_addons_path()

if MAKE_GIT_CLEAN == "1":
    # clean
    subprocess.check_call(["git", "checkout", "-f", BRANCH], cwd=OpenupgradeDir)
    subprocess.check_call(["git", "clean", "-xdff", BRANCH], cwd=OpenupgradeDir)  # remove old pyc files
    # apply patches
    root = os.path.join(os.environ['ACTIVE_CUSTOMS'], 'migration', VERSION)
    for file in os.listdir(root):
        if file.endswith(".patch"):
            subprocess.check_call(["git", "apply", os.path.join(root, file)], cwd=OpenupgradeDir)
os.chdir("/opt/odoo_home/repos/openupgradelib")
if float(os.getenv("ODOO_VERSION", "")) >= 11.0:
    os.system("python3 setup.py install")
else:
    os.system("python setup.py install")

os.chdir(OpenupgradeDir)
subprocess.Popen([
    'sudo',
    '-E',
    '-H',
    '-u',
    os.environ["ODOO_USER"]
    ] + CMD, cwd=OpenupgradeDir).wait()
