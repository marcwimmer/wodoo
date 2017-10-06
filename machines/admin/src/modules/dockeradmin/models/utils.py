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

def get_submodules(path):
    submodules = subprocess.check_output(['/usr/bin/git', 'submodule'], cwd=path)
    for line in submodules.split("\n"):
        if not line:
            continue
        line = line.strip()
        line = line.split(" ")
        branch = get_branch(os.path.join(path, line[1]))
        yield {
            'name': line[1],
            'revision': line[0],
            'branch': branch,
        }

def get_branch(path):
    return subprocess.check_output(['/usr/bin/git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=path).strip()

def is_branch_merged(path, which_branch, to_branch):
    out = subprocess.check_output(['/usr/bin/git', 'branch', '--merged', to_branch], cwd=path).strip()
    out = [x for x in out if out.strip() == which_branch]

    return bool(out)

def new_branch(path, branch_name):
    subprocess.check_call(['odoo-git', 'new-ticket'], cwd=path).strip()
