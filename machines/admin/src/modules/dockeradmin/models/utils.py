import os
import json
import subprocess

def get_containers():
    containers = json.loads(subprocess.check_output(['/usr/bin/curl', '--unix-socket', '/var/run/docker.sock', 'http:/containers/json']))

    return containers

def restart_container(name):
    """
    :param name: e.g. odoo, asterisk
    """
    stop_container(name)
    start_container(name)

def start_container(name):
    """
    :param name: e.g. odoo, asterisk
    """
    subprocess.check_call([os.path.join(os.environ['ODOO_HOME'], 'odoo'), 'up', '-d', name], cwd=os.environ['ODOO_HOME'])

def stop_container(name):
    """
    :param name: e.g. odoo, asterisk
    """
    subprocess.check_call([os.path.join(os.environ['ODOO_HOME'], 'odoo'), 'kill', name], cwd=os.environ['ODOO_HOME'])
