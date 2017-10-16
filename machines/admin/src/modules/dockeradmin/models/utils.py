# -*- coding: utf-8 -*-
import os
import json
import subprocess
import traceback
import logging

logger = logging.getLogger(__name__)

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
    out = subprocess.check_output(['/usr/bin/git', 'branch', '--merged', to_branch], cwd=path).split("\n")
    out = [x.strip() for x in out]
    out = [x for x in out if x == which_branch.name]

    return bool(out)

def new_branch(path, branch_name):
    subprocess.check_call(['odoo-git', 'new-ticket'], cwd=path)

def force_switch_branch(path, branch_name):
    subprocess.check_call(['/usr/bin/git', 'checkout', branch_name, '-f'], cwd=path)
    os.system('sync')
    subprocess.check_call(['/usr/bin/git', 'clean', '-xdff'], cwd=path)

def git_pull(path):
    subprocess.check_call(['/usr/bin/git', 'pull'], cwd=path)

def git_push(path):
    subprocess.check_call(['/usr/bin/git', 'push'], cwd=path)

def merge(path, which_branch, on_this_branch):
    try:
        force_switch_branch(path, which_branch)
        git_pull(path)
        force_switch_branch(path, on_this_branch)
        git_pull(path)
        os.system('git config --global user.email "admin-console@odoo"')
        os.system('git config --global user.name "admin-console-odoo"')
        os.environ['GIT_MERGE_AUTOEDIT'] = 'no'
        subprocess.check_call(['/usr/bin/git', 'merge', which_branch], cwd=path)
        git_push(path)

    except:
        msg = traceback.format_exc()
        logger.error(msg)
        raise
    finally:
        force_switch_branch(path, 'deploy')
