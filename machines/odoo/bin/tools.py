import sys
from consts import ODOO_USER
import subprocess
import os
from module_tools import odoo_config
from module_tools.odoo_config import customs_dir
from pathlib import Path
pidfile = Path('/tmp/odoo.pid')
config = odoo_config.get_env()
version = odoo_config.current_version()


def _replace_params_in_config(ADDONS_PATHS, file):
    if not os.getenv("DB_HOST") or not os.getenv("DB_USER"):
        raise Exception("Please define all DB Env Variables!")
    content = file.read_text()
    content = content.replace("__ADDONS_PATH__", ADDONS_PATHS)

    server_wide_modules = (os.environ['SERVER_WIDE_MODULES'] or '').split(',')
    if os.getenv("IS_ODOO_CRONJOB", "") == "1" or 'debug' in file.name:
        server_wide_modules = list(filter(lambda x: x != 'queue_job', server_wide_modules))
    server_wide_modules = ','.join(server_wide_modules)
    content = content.replace("__SERVER_WIDE_MODULES__", server_wide_modules)

    if 'without_demo=' not in content:
        if os.getenv("ODOO_DEMO", "") == "1":
            content = content + "\nwithout_demo=False"
        else:
            content = content + "\nwithout_demo=all"

    for key in [
        "DB_USER", "DB_PWD", "DB_MAXCONN",
        "DB_PORT", "DB_HOST", "ODOO_MAX_CRON_THREADS"
    ]:
        content = content.replace("__{}__".format(key), os.getenv(key, ""))

    file.write_text(content)

def _run_autosetup():
    print("Executing autosetup...")
    path = customs_dir() / 'autosetup'
    if path.exists():
        for file in path.glob("*.sh"):
            print("executing {}".format(file))
            os.chdir(path.parent)
            subprocess.check_call([
                file,
                os.environ['ODOO_AUTOSETUP_PARAM'],
            ])
    print("Done autosetup")

def _replace_variables_in_config_files():
    ADDONS_PATHS = ','.join(list(map(str, odoo_config.get_odoo_addons_paths())))
    for file in Path(os.getenv("ODOO_CONFIG_DIR")).glob("config_*"):
        _replace_params_in_config(ADDONS_PATHS, file)

def _run_libreoffice_in_background():
    subprocess.Popen(["/bin/bash", os.environ['ODOOLIB'] + "/run_soffice.sh"])

def get_config_file(confname):
    return str(Path(os.environ['ODOO_CONFIG_DIR']) / confname)

def prepare_run():
    _replace_variables_in_config_files()

    if config['RUN_AUTOSETUP'] == "1":
        _run_autosetup()

    _run_libreoffice_in_background()


def get_odoo_bin(for_shell=False):
    is_odoo_cronjob = os.getenv("IS_ODOO_CRONJOB", "")
    is_odoo_queuejob = os.getenv("IS_ODOO_QUEUEJOB", "")

    if is_odoo_cronjob and not config.get('RUN_ODOO_CRONJOB') == '1':
        print("Cronjobs shall not run. Good-bye!")
        sys.exit(0)

    if is_odoo_queuejob and not config.get("RUN_ODOO_QUEUEJOB") == "1":
        print("Queue-Jobs shall not run. Good-bye!")
        sys.exit(0)

    EXEC = "odoo-bin"
    GEVENT_MARKER = ""
    if is_odoo_cronjob:
        print('Starting odoo cronjobs')
        CONFIG = "config_cronjob"
        if version <= 9.0:
            EXEC = "openerp-server"

    elif is_odoo_queuejob:
        print('Starting odoo queuejobs')
        CONFIG = 'config_queuejob'

    else:
        print('Starting odoo web')
        CONFIG = 'config_webserver'
        if version <= 9.0:
            if for_shell:
                EXEC = "openerp-server"
            else:
                EXEC = "openerp-gevent"
        else:
            GEVENT_MARKER = "gevent" if config["ODOO_GEVENT_MODE"] == "1" else ""

    EXEC = "{}/{}".format(
        os.environ["SERVER_DIR"],
        EXEC
    )

    return EXEC, CONFIG, GEVENT_MARKER

def kill_odoo():
    if pidfile.exists():
        print("Killing Odoo")
        pid = pidfile.read_text()
        subprocess.call([
            '/usr/bin/sudo',
            '/bin/kill',
            '-9',
            pid
        ])
        pidfile.unlink()
    else:
        if version <= 9.0:
            subprocess.call([
                '/usr/bin/sudo',
                '/usr/bin/pkill',
                '-9',
                '-f',
                'openerp-server',
            ])
            subprocess.call([
                '/usr/bin/sudo',
                '/usr/bin/pkill',
                '-9',
                '-f',
                'openerp-gevent',
            ])

def __python_exe():
    if version <= 10.0:
        return "/usr/bin/python"
    else:
        return "/usr/bin/python3"

def exec_odoo(CONFIG, *args, force_no_gevent=False, odoo_shell=False, **kwargs): # NOQA

    assert not [x for x in args if '--pidfile' in x], "Not custom pidfile allowed"

    kill_odoo()

    EXEC, _CONFIG, GEVENT_MARKER = get_odoo_bin(for_shell=odoo_shell)
    CONFIG = get_config_file(CONFIG or _CONFIG)
    cmd = [
        "/usr/bin/sudo",
        "-E",
        "-H",
        "-u",
        ODOO_USER,
        __python_exe(),
        EXEC,
    ]
    if not odoo_shell and (GEVENT_MARKER and not force_no_gevent):
        cmd += [GEVENT_MARKER]
    if odoo_shell:
        cmd += ['shell']
    cmd += [
        '-c',
        CONFIG,
        '-d',
        config["DBNAME"],
    ]
    if not odoo_shell:
        cmd += [
            '--pidfile={}'.format(pidfile),
        ]
    cmd += args

    subprocess.call(cmd, **kwargs)
    if pidfile.exists():
        pidfile.unlink()
