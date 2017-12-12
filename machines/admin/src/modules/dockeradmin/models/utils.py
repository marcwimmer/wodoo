# -*- coding: utf-8 -*-
import os
import json
import subprocess
import traceback
import logging

logger = logging.getLogger(__name__)

def execute_odoo(*params):
    try:
        local_odoo_home, host_odoo_home, working_dir = os.getenv("ODOO_HOME", ""), os.getenv('HOST_ODOO_HOME', ""), os.getenv('WORKING_DIR', "")
        os.environ['ODOO_HOME'] = host_odoo_home
        os.environ['WORKING_DIR'] = host_odoo_home
        proc = subprocess.Popen([os.path.join(local_odoo_home, 'odoo')] + list(params), cwd=local_odoo_home)
        std, err = proc.communicate()
        if err:
            raise Exception(std + "\n=================================\n" + err)
    except Exception:
        msg = traceback.format_exc()
        raise Exception(msg)
    finally:
        os.environ['ODOO_HOME'] = local_odoo_home
        os.environ['WORKING_DIR'] = working_dir

def compose():
    """
    Updates the main docker compose file. Necessary after updating
    the instances.
    """
    execute_odoo("compose")

def get_root_path():
    return os.path.join(os.environ["ODOO_HOME"], 'data', 'src', 'customs', os.environ['CUSTOMS'])

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
    execute_odoo("up", "-d", name)

def stop_container(name):
    """
    :param name: e.g. odoo, asterisk
    """
    execute_odoo("kill", name)

def get_submodules(path=get_root_path()):
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

def get_branch(path=get_root_path()):
    return subprocess.check_output(['/usr/bin/git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=path).strip()

def is_branch_merged(which_branch, to_branch, path=get_root_path()):
    out = subprocess.check_output(['/usr/bin/git', 'branch', '--merged', to_branch], cwd=path).split("\n")
    out = [x.strip() for x in out]
    out = [x for x in out if x == which_branch.name]

    return bool(out)

def new_branch(branch_name, path=get_root_path()):
    raise Exception('todo')
    subprocess.check_call(['odoo-git', 'new-ticket'], cwd=path)

def switch_branch(branch_name, force=False, path=get_root_path()):
    subprocess.check_call(['/usr/bin/git', 'checkout', branch_name, '-f' if force else ''], cwd=path)
    os.system('sync')
    subprocess.check_call(['/usr/bin/git', 'clean', '-xdff'], cwd=path)

def git_pull(path=get_root_path()):
    subprocess.check_call(['/usr/bin/git', 'pull'], cwd=path)

def git_push(path=get_root_path()):
    subprocess.check_call(['/usr/bin/git', 'push'], cwd=path)

def git_fetch(path=get_root_path()):
    subprocess.check_call(['/usr/bin/git', 'fetch'], cwd=path)

def git_checkout(path, cwd=get_root_path(), force=False):
    subprocess.check_call(['/usr/bin/git', 'checkout', '-f' if force else '', path], cwd=cwd)

def git_add(path, cwd=get_root_path()):
    subprocess.check_call(['/usr/bin/git', 'add', path], cwd=cwd)

def git_set_user(username):
    subprocess.check_call(['/usr/bin/git', 'config', '--global', 'user.email', username])
    subprocess.check_call(['/usr/bin/git', 'config', '--global', 'user.name', username])

def git_commit(username, message, cwd=get_root_path()):
    git_set_user()
    subprocess.check_call(['/usr/bin/git', 'commit', '-m', message or '<empty message>'], cwd=cwd)

def merge(username, which_branch, on_this_branch, path=get_root_path()):
    was_branch = get_branch()
    try:
        os.environ['GIT_MERGE_AUTOEDIT'] = 'no'
        git_set_user(username)
        switch_branch(which_branch, force=True)
        git_pull(path)
        switch_branch(on_this_branch, force=True)
        git_pull(path)
        subprocess.check_call(['/usr/bin/git', 'merge', which_branch], cwd=path)
        git_push(path)

    except Exception:
        msg = traceback.format_exc()
        logger.error(msg)
        raise
    finally:
        switch_branch(was_branch, force=True)

def git_state(path=get_root_path()):
    return subprocess.check_output(['/usr/bin/git', 'status'], cwd=path)
