import sys
import psutil
import importlib
import os
import subprocess
from pathlib import Path
from .myconfigparser import MyConfigParser  # NOQA
try:
    import click
except ImportError: click = None

def _get_default_anticipated_host_run_dir(WORKING_DIR, PROJECT_NAME):
    if WORKING_DIR and (WORKING_DIR / '.odoo').exists():
        if click:
            click.secho("Using local run-directory - should only be used for non productive setups!", fg='yellow')
            click.secho("If this is not intended, then remove the .odoo sub-directory please!", fg='yellow')
        return WORKING_DIR / '.odoo' / 'run'
    if "HOST_HOME" in os.environ:
        HOME_DIR = Path(os.environ['HOST_HOME'])
    else:
        HOME_DIR = Path(os.path.expanduser("~"))
    if not PROJECT_NAME:
        return None
    return HOME_DIR / '.odoo' / 'run' / PROJECT_NAME

def get_use_docker(files):
    try:
        myconfig = MyConfigParser(files['settings'])
    except Exception:
        USE_DOCKER = True
    else:
        USE_DOCKER = myconfig.get("USE_DOCKER", "1") == "1"

    return USE_DOCKER

def load_dynamic_modules(parent_dir):
    for module in parent_dir.glob("**/__commands.py"):
        if module.is_dir():
            continue
        spec = importlib.util.spec_from_file_location(
            "dynamic_loaded_module", str(module),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

def _search_path(filename):
    filename = Path(filename)
    filename = filename.name
    for path in os.environ['PATH'].split(":"):
        path = Path(path)
        if (path / filename).exists():
            return str(path / filename)

def _get_customs_root(p):
    # arg_dir = p
    if p:
        while len(p.parts) > 1:
            if (p / 'MANIFEST').exists():
                return p
            p = p.parent
    # click.echo("Missing MANIFEST - file here in {}".format(arg_dir))

def _get_project_name(config, p):
    if not p:
        return

    from .settings import _get_settings
    with _get_settings(config, None) as config:
        project_name = config.get("PROJECT_NAME", "")
        if project_name:
            return project_name
        DEVMODE = config.get("DEVMODE", "") == "1"

    if DEVMODE:
        return p.name

    if (p / '.git').exists():
        branch_name = subprocess.check_output([
            'git',
            'rev-parse',
            '--abbrev-ref',
            'HEAD'
        ], cwd=str(p)).decode('utf-8').strip()
    else:
        branch_name = ""
    if branch_name and branch_name not in [
        'master',
        'deploy',
        'stage',
    ]:
        branch_name = 'dev'
    return "_".join(x for x in [
        p.name,
        branch_name
    ] if x)

def make_absolute_paths(config, dirs, files, commands):
    from .consts import default_dirs, default_files, default_commands
    for (input, output) in [
        (default_dirs, dirs),
        (default_files, files),
        (default_commands, commands)
    ]:
        output.clear()
        for k, v in input.items():
            output[k] = v

    dirs['odoo_home'] = Path(os.environ['ODOO_HOME'])

    def make_absolute(d, key_values={}):
        for k, v in list(d.items()):
            if not v:
                continue
            skip = False
            for k2, v2 in key_values.items():
                p = "${{{}}}".format(k2)
                if p in str(v):
                    v = v.replace(p, str(v2))

            for value, name in [
                (config.HOST_RUN_DIR, '${run}'),
                (config.PROJECT_NAME, '${project_name}'),
            ]:
                if name in str(v):
                    if value:
                        v = str(v).replace(name, str(value))
                    else:
                        del d[k]
                        skip = True
                        break
            if skip:
                continue
            if str(v).startswith("~"):
                v = Path(os.path.expanduser(str(v)))

            if not str(v).startswith('/'):
                v = dirs['odoo_home'] / v
            d[k] = Path(v)

    make_absolute(dirs)
    make_absolute(files, dirs)

    # dirs['host_working_dir'] = os.getenv('LOCAL_WORKING_DIR', "")
    if 'docker_compose' in files:
        commands['dc'] = [x.replace("$docker_compose_file", str(files['docker_compose'])) for x in commands['dc'] if x]

def set_shell_table_title(PROJECT_NAME):
    if os.getenv("DOCKER_MACHINE", "") != "1":
        parent = psutil.Process(psutil.Process(os.getpid()).ppid())
        parent_process_name = parent.name()
        if parent_process_name in ['sh', 'bash', 'zsh']:
            tab_title = "odoo - {}".format(PROJECT_NAME)
            print("\033]0;{}\007".format(tab_title), file=sys.stdout) # NOQA
