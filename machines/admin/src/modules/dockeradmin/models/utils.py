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
    subprocess.check_call(['odoo', 'kill', name], cwd=os.environ['ODOO_HOME'])
    subprocess.check_call(['odoo', 'up', '-d', name], cwd=os.environ['ODOO_HOME'])
