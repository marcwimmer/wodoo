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

def update_server_conf():
    filepath = os.getenv('OVPN_SERVER_CONF', "")
    if filepath:
        with open(filepath, 'r') as f:
            content = f.read()
        content = content.replace("__IP_POOL_START__", config['ip_pool']['start'])
        content = content.replace("__IP_POOL_END", config['ip_pool']['end'])
        content = content.replace("__IP_POOL_NETMASK", config['ip_pool']['netmask'])
        with open(filepath, 'w') as f:
            f.write(content)


if __name__ == '__main__':
    update_server_conf()
