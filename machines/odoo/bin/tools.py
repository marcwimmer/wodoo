import sys
from consts import ODOO_USER
import subprocess
import os
from module_tools import odoo_config
from module_tools.odoo_config import customs_dir
from pathlib import Path
pidfile = Path('/var/run/odoo.pid')
config = odoo_config.get_env()


def _replace_params_in_config(ADDONS_PATHS, file):
    if not os.getenv("DB_HOST") or not os.getenv("DB_USER"):
        raise Exception("Please define all DB Env Variables!")
    content = file.read_text()
    content = content.replace("__ADDONS_PATH__", ADDONS_PATHS)

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
    ADDONS_PATHS = ','.join(filter(lambda t: t, list(map(str, odoo_config.get_odoo_addons_paths())) + [str(odoo_config.customs_dir() / 'links')]))
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


def get_odoo_bin():
    is_odoo_cronjob = os.getenv("IS_ODOO_CRONJOB", "")
    is_odoo_queuejob = os.getenv("IS_ODOO_QUEUEJOB", "")

    if is_odoo_cronjob and not config.run_odoo_cronjob:
        print("Cronjobs shall not run. Good-bye!")
        sys.exit(0)

    if is_odoo_queuejob and not config.run_odoo_queuejob:
        print("Queue-Jobs shall not run. Good-bye!")
        sys.exit(0)

    EXEC = "odoo-bin"
    GEVENT_MARKER = ""
    if is_odoo_cronjob:
        print('Starting odoo cronjobs')
        CONFIG = "config_cronjob"
        EXEC = os.environ["ODOO_EXECUTABLE_CRONJOBS"]
        if odoo_config.current_version() <= 9.0:
            EXEC = "openerp-server"

    elif is_odoo_queuejob:
        print('Starting odoo queuejobs')
        CONFIG = 'config_queuejob'

    else:
        print('Starting odoo web')
        CONFIG = 'config_webserver'
        if odoo_config.current_version() <= 9.0:
            EXEC = "openerp-gevent"
        else:
            GEVENT_MARKER = "gevent" if config["ODOO_GEVENT_MODE"] == "1" else ""

    EXEC = "{}/{}".format(
        os.environ["SERVER_DIR"],
        EXEC
    )

    return EXEC, CONFIG, GEVENT_MARKER


def exec_odoo(CONFIG, *args, env={}):
    from pudb import set_trace
    set_trace()

    assert not [x for x in args if '--pidfile' in x], "Not custom pidfile allowed"

    if pidfile.exists():
        if pidfile.exists():
            pid = pidfile.read_text()
            subprocess.call([
                '/usr/bin/sudo',
                '/usr/bin/kill',
                '-9',
                pid
            ])
            pidfile.unlink()

    EXEC, _CONFIG, GEVENT_MARKER = get_odoo_bin()
    CONFIG = get_config_file(CONFIG or _CONFIG)
    cmd = [
        "/usr/bin/sudo",
        "-E",
        "-H",
        "-u",
        ODOO_USER,
        EXEC,
    ]
    if GEVENT_MARKER:
        cmd += [GEVENT_MARKER]
    cmd += [
        '-c',
        CONFIG,
        '-d',
        config["DBNAME"],
        '--pidfile={}'.format(pidfile),
    ]

    subprocess.check_call(cmd)
