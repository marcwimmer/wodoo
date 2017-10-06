# called by manage.sh bash script; replaces $ALL_CONFIG_FILES
import os
import shutil
import re
import sys
import tempfile
from yaml import load, dump
from datetime import datetime
import hiyapyco
import subprocess
import inspect
odoo_home = os.environ['ODOO_HOME']

paths = os.environ['ALL_CONFIG_FILES'].split("\n")

dest_file = sys.argv[1]

temp_files = set()
tempdir = tempfile.mkdtemp()

if not dest_file:
    raise Exception('require destination path')

with open(dest_file, 'w') as f:
    f.write("#Composed {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    f.write("version: '3.3'\n")

def replace_all_envs_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    all_params = re.findall(r'\$\{[^\}]*?\}', content)
    for param in all_params:
        name = param
        name = name.replace("${", "")
        name = name.replace("}", "")
        content = content.replace(param, os.environ[name])
    with open(filepath, 'w') as f:
        f.write(content)


for path in set(paths):
    filename = os.path.basename(path)

    def use_file():
        if 'run_' in filename:
            run = re.findall(r'run_[^\.]*', filename)
            if run:
                if os.getenv(run[0].upper(), "1") == "1":
                    return True
            return False
        else:
            return True

    if not use_file():
        continue

    with open(path, 'r') as f:
        content = f.read()
        # dont matter if written manage-order: or manage-order
        if 'manage-order' not in content:
            order = '99999999'
        else:
            order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
    folder_name = os.path.basename(os.path.dirname(path))
    if os.getenv("RUN_{}".format(folder_name.upper()), "1") == "0":
        continue

    order = str(order)

    # put all files in their order into the temp directory
    counter = 0
    temp_path = ""
    while not temp_path or os.path.exists(temp_path):
        counter += 1
        temp_path = os.path.join(tempdir, '{}-{}'.format(order, str(counter).zfill(5)))

    with open(temp_path, 'w') as dest:
        with open(path, 'r') as source:
            j = load(source.read())
            # TODO complain version - override version
            j['version'] = '3.3'
            dest.write(dump(j, default_flow_style=False))
            dest.write("\n")
    replace_all_envs_in_file(temp_path)
    temp_files.add(os.path.basename(temp_path))
    del temp_path


files = sorted(temp_files, key=lambda x: float(x.split("/")[-1].replace("-", ".")))
cmdline = []
cmdline.append("/usr/local/bin/docker-compose")
for file in files:
    cmdline.append('-f')
    cmdline.append(os.path.join(os.path.basename(tempdir), file))
cmdline.append('config')
shutil.move(tempdir, odoo_home)
try:
    proc = subprocess.Popen(cmdline, cwd=odoo_home, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    conf, err = proc.communicate()
    if err:
        print err
        raise Exception(err)
except:
    raise
else:
    with open(dest_file, 'w') as f:
        f.write(conf)
finally:
    shutil.move(os.path.join(odoo_home, os.path.basename(tempdir)), tempdir)
    shutil.rmtree(tempdir)
