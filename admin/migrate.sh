#!/usr/bin/python
# executed in odoo container
import json
import pipes
import sys
import os
import pickle
import subprocess
import base64
e, BRANCH, CMD, ADDONS_PATH, VERSION, MAKE_GIT_CLEAN, PULL_LATEST = sys.argv
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

path_shas = os.path.join(os.environ['ACTIVE_CUSTOMS'], 'migration.sha')

import pudb;pudb.set_trace()
if MAKE_GIT_CLEAN == "1":
    # clean
    subprocess.check_call(["git", "checkout", "-f", BRANCH], cwd=OpenupgradeDir)
    if PULL_LATEST == '1':
        subprocess.check_call(["git", "pull"], cwd=OpenupgradeDir)
    else:
        if os.path.exists(path_shas):
            with open(path_shas, 'r') as f:
                shas = json.loads(f.read())
            sha = shas.get(os.environ['ODOO_VERSION'], False)
            if sha:
                subprocess.check_call(["git", "checkout", "-f", sha], cwd=OpenupgradeDir)

    subprocess.check_call(["git", "clean", "-xdff", BRANCH], cwd=OpenupgradeDir)  # remove old pyc files
    # apply patches
    root = os.path.join(os.environ['ACTIVE_CUSTOMS'], 'migration', VERSION)
    for file in os.listdir(root):
        if file.endswith(".patch"):
            subprocess.check_call(["git", "apply", os.path.join(root, file)], cwd=OpenupgradeDir)

    def store_sha():
        # store the used SHA migration tag
        SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=OpenupgradeDir).strip()
        if not os.path.exists(path_shas):
            with open(path_shas, 'w') as f:
                f.write("{}")
        with open(path_shas, 'r') as f:
            shas = json.loads(f.read())
        shas[os.environ['ODOO_VERSION']] = SHA
        with open(path_shas, 'w') as f:
            f.write(json.dumps(shas))
    store_sha()

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
