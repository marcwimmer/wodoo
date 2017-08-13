# called by manage.sh bash script; replaces $ALL_CONFIG_FILES
import os
import shutil
import re
paths = os.environ['ALL_CONFIG_FILES'].split("\n")
dest_files = []

for path in paths:
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
        order = content.split("manage-order")[1].split("\n")[0].replace(":", "").strip()
    folder_name = os.path.basename(os.path.dirname(path))
    if os.getenv("RUN_{}".format(folder_name.upper()), "1") == "0":
        continue
    dest_file = 'run/{}-docker-compose.{}.yml'.format(order, folder_name)
    shutil.copy(path, dest_file)
    dest_files.append(dest_file)
for x in sorted(dest_files):
    print x.replace("run/", "")
