#!/usr/bin/python
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

shutil.copy(os.path.join(root_path, 'machines/openvpn/docker-compose.yml.tmpl'), os.path.join(root_path, dest_docker_file))

# set parameters in docker compose template

with open(os.path.join(root_path, dest_docker_file), 'r') as f:
    content = f.read()
content = content.replace("${OVPN_DOMAIN}", domain)
content = os.path.expandvars(content)
with open(os.path.join(root_path, dest_docker_file), 'w') as f:
    f.write(content)

with open(os.path.join(root_path, 'machines/openvpn/nginx.subdomain.tmpl'), 'r') as f:
    subdomain = f.read()
    subdomain = subdomain.replace("${DOMAIN}", domain)

    for line in subdomain.split("\n"):
        if not line:
            continue
        splitted = line.split(" ")
        subdomain = splitted[0]
        machine = splitted[1]
        port = splitted[2]
        out = subprocess.check_output([
            os.path.join(root_path, 'machines/nginx/add_nginx_subdomain.sh'),
            subdomain,
            machine,
            port,
            os.path.join(root_path, 'run/nginx_subdomains'),
            'ovpn.{domain}.subdomain'.format(domain=domain)
        ])
        print '--------------------------------'
        print out

with open(results, 'w') as f:
    f.write(dest_docker_file)
