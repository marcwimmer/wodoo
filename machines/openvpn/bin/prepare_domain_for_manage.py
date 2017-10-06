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
import yaml
docker_compose_file = sys.argv[1]
filepath_config = sys.argv[2]
root_path = sys.argv[3]

template_file = os.path.join(root_path, 'machines/openvpn/template.yml')

with open(filepath_config, 'r') as f:
    config = json.loads(f.read())

domain = config['domain']
with open(docker_compose_file, 'r') as f:
    docker_config = yaml.load(f.read())

with open(template_file, 'r') as f:
    ovpn_services = f.read()

ovpn_services = ovpn_services.replace("${OVPN_DOMAIN}", domain)
ovpn_services = ovpn_services.replace("${OVPN_CONFIG_FILE}", os.path.realpath(filepath_config).strip())
ovpn_services = os.path.expandvars(ovpn_services)
ovpn_services = yaml.load(ovpn_services)

for service in ovpn_services['services']:
    docker_config['services'][service] = ovpn_services['services'][service]

with open(docker_compose_file, 'w') as f:
    f.write(yaml.dump(docker_config, default_flow_style=False))

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
            'ovpn.{domain}'.format(domain=domain),
            'default',
        ])
