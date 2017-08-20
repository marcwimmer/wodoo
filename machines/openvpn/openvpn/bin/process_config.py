# -*- coding: utf-8 -*-
import os
import sys
import json
import shutil
import subprocess
import iptools.ipv4 as iptools

CONFIG_FILE = os.getenv('CONFIG_FILEPATH', '...........')

with open(CONFIG_FILE, 'r') as f:
    config = json.loads(f.read())

def get_next_ip(offset):
    start = config['ip_pool']['start']
    l = iptools.ip2long(start)
    l += offset
    return iptools.long2ip(l)

def setup_ccd(name, dns=None, fixed_ip=None):
    with open(os.path.join(os.environ['PATH_CCD'], name), 'w') as f:
        if fixed_ip:
            f.write("ifconfig-push {} {}\n".format(fixed_ip, config['ip_pool']['netmask']))
        if dns:
            f.write("push \"dhcp-option DNS {}\"\n".format(dns))


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


def make_default_client_confs():
    for internal_host, internal_host_ip in config.get("internal_hosts", {}).items():
        setup_ccd(internal_host, fixed_ip=internal_host_ip)

        # get ovpn config for internal remote
        CONFIG_TEMPLATE_INTERNAL_REMOTE = os.environ['CONFIG_TEMPLATE_INTERNAL_REMOTE']

        dest_conf_name = "{ovpn_domain}_{internal_hostname}".format(
            ovpn_domain=os.environ['OVPN_DOMAIN'],
            internal_hostname=internal_host
        )

        subprocess.check_output([
            '/usr/local/bin/make_client_key.sh',
            internal_host,
            '-silent',
        ])
        subprocess.check_output([
            '/usr/local/bin/pack_client_conf.sh',
            internal_host,
            CONFIG_TEMPLATE_INTERNAL_REMOTE,
            dest_conf_name,
        ])


if __name__ == '__main__':
    update_server_conf()

    make_default_client_confs()
