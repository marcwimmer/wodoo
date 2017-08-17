import os
import sys
import json

CONFIG_FILE = os.getenv('CONFIG_FILEPATH', '...........')
PATH_CCD = os.environ['PATH_CCD']

with open(CONFIG_FILE, 'r') as f:
    config = json.loads(f.read())


def setup_ccd(name, dns=None, fixed_ip=None):
    with open(name, 'w') as f:
        if fixed_ip:
            f.write("ifconfig-push {} {}\n".format(fixed_ip, config['ip_pool']['netmask']))
        if dns:
            f.write("push \"dhcp-option DNS {}\"\n".format(dns))


for internal_host, internal_host_ip in config.get("internal_hosts", {}).items():
    # TODO check if ip is in range
    setup_ccd(internal_host, fixed_ip=internal_host_ip)
