#!/usr/bin/python
#
# After the docker-compose files are prepared and lie in
# /run/docker-compose.xxxx.yml, this script generates an instance of the
# openvpn services for each openvpn domain. Domains are for example asterisk.
#
# The resulting files also lie in /run/9999-....
#
# Each domain has is own subnet and ip addresses.
#

import os
import sys
import json
import shutil
import subprocess
import tempfile
results = sys.argv[1]
filepath_config = sys.argv[2]
root_path = sys.argv[3]

with open(filepath_config, 'r') as f:
    config = json.loads(f.read())

domain = config['domain']
dest_docker_file = 'run/9999-docker-compose.ovpn.{}.yml'.format(domain)

shutil.copy(os.path.join(root_path, 'machines/openvpn/template.yml'), os.path.join(root_path, dest_docker_file))

# set parameters in docker compose template

with open(os.path.join(root_path, dest_docker_file), 'r') as f:
    content = f.read()
content = content.replace("${OVPN_DOMAIN}", domain)
content = content.replace("${OVPN_CONFIG_FILE}", os.path.realpath(filepath_config).strip())
content = os.path.expandvars(content)
with open(os.path.join(root_path, dest_docker_file), 'w') as f:
    f.write(content)

with open(os.path.join(root_path, 'machines/openvpn/nginx.path.tmpl'), 'r') as f:
    path = f.read()
    path = path.replace("${DOMAIN}", domain)

    for line in path.split("\n"):
        if not line:
            continue
        splitted = line.split(" ")
        path = splitted[0]
        machine = splitted[1]
        port = splitted[2]
        subprocess.check_call([
            os.path.join(root_path, 'machines/nginx/add_nginx_path.sh'),
            path,
            machine,
            port,
            os.path.join(root_path, 'run/nginx_paths'),
            'ovpn.{domain}.path'.format(domain=domain)
        ])

with open(results, 'w') as f:
    f.write(dest_docker_file)
