#!/usr/bin/python
import os
import sys
import json
import shutil
filepath_config = sys.argv[1]
root_path = sys.argv[2]

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
with open(os.path.join(root_path, 'run/nginx_subdomains/ovpn.{domain}.subdomain'.format(domain=domain)), 'w') as f:
    f.write(subdomain)

print dest_docker_file
