import tempfile
import shutil
import requests
import time
import threading
import sys
from consts import ODOO_USER
import subprocess
import os
from odoo_tools import odoo_config
from odoo_tools.odoo_config import customs_dir
from odoo_tools.odoo_config import get_conn_autoclose
from pathlib import Path
pidfile = Path('/tmp/odoo.pid')
config = odoo_config.get_env()
version = odoo_config.current_version()

is_odoo_cronjob = os.getenv("IS_ODOO_CRONJOB", "0") == "1"
is_odoo_queuejob = os.getenv("IS_ODOO_QUEUEJOB", "0") == "1"

def _replace_params_in_config(ADDONS_PATHS, file):
    if not config.get("DB_HOST", "") or not config.get("DB_USER", ""):
        raise Exception("Please define all DB Env Variables!")
    content = file.read_text()
    content = content.replace("__ADDONS_PATH__", ADDONS_PATHS)
    if config['ODOO_ADMIN_PASSWORD']:
        content += "\nadmin_passwd = " + config['ODOO_ADMIN_PASSWORD']
    content = content.replace("__ENABLE_DB_MANAGER__", 'True' if config['ODOO_ENABLE_DB_MANAGER'] == '1' else 'False')

    server_wide_modules = (os.getenv('SERVER_WIDE_MODULES', '') or '').split(',')
    if os.getenv("IS_ODOO_QUEUEJOB", "") == "1" and 'debug' not in file.name:
        server_wide_modules += ['queue_job']
    if os.getenv("IS_ODOO_QUEUEJOB", "") != "1" or 'debug' in file.name:
        if 'queue_job' in server_wide_modules:
            server_wide_modules.remove('queue_job')
    server_wide_modules = ','.join(server_wide_modules)
    content = content.replace("__SERVER_WIDE_MODULES__", server_wide_modules)

    for key, value in os.environ.items():
        key = f'__{key}__'
        content = content.replace(key, value)

    if 'without_demo=' not in content:
        if os.getenv("ODOO_DEMO", "") == "1":
            content = content + "\nwithout_demo=False"
        else:
            content = content + "\nwithout_demo=all"

    for key in config.keys():
        content = content.replace("__{}__".format(key), config[key])
    for key in os.environ.keys():
        content = content.replace("__{}__".format(key), os.getenv(key, ""))

    file.write_text(content)

def _run_autosetup():
    path = customs_dir() / 'autosetup'
    if path.exists():
        for file in path.glob("*.sh"):
            print("executing {}".format(file))
            os.chdir(path.parent)
            subprocess.check_call([
                file,
                os.environ['ODOO_AUTOSETUP_PARAM'],
            ])

def _replace_variables_in_config_files(config):
    config_dir = Path(os.environ['ODOO_CONFIG_DIR'])
    config_dir_template = Path(os.environ['ODOO_CONFIG_TEMPLATE_DIR'])
    config_dir.mkdir(exist_ok=True, parents=True)
    for file in config_dir_template.glob("*"):
        path = str(config_dir / file.name)
        shutil.copy(str(file), path)
        subprocess.call(['chmod', 'a+r', path])
        del path

    no_extra_addons_paths = False
    if config and config.no_extra_addons_paths:
        no_extra_addons_paths = True
    ADDONS_PATHS = ','.join(list(map(str, odoo_config.get_odoo_addons_paths(
        no_extra_addons_paths=no_extra_addons_paths
    ))))

    config_dir = Path(os.getenv("ODOO_CONFIG_DIR"))
    common_content = (config_dir / 'common').read_text()
    for file in config_dir.glob("config_*"):
        content = file.read_text()
        file.write_text(common_content + "\n" + content)
        _replace_params_in_config(ADDONS_PATHS, file)

def _run_libreoffice_in_background():
    subprocess.Popen(["/bin/bash", os.environ['ODOOLIB'] + "/run_soffice.sh"])

def get_config_file(confname):
    return str(Path(os.environ['ODOO_CONFIG_DIR']) / confname)

def prepare_run(local_config=None):

    _replace_variables_in_config_files(local_config)

    if config['RUN_AUTOSETUP'] == "1":
        _run_autosetup()

    _run_libreoffice_in_background()

    # make sure out dir is owned by odoo user to be writable
    user_id = int(os.getenv('OWNER_UID', os.getuid()))
    for path in [
        os.environ['OUT_DIR'],
        os.environ['RUN_DIR'],
        os.environ['ODOO_DATA_DIR'],
        os.getenv('INTERCOM_DIR', ''),
        Path(os.environ['RUN_DIR']) / 'debug',
        Path(os.environ['ODOO_DATA_DIR']) / 'addons',
        Path(os.environ['ODOO_DATA_DIR']) / 'filestore',
        Path(os.environ['ODOO_DATA_DIR']) / 'sessions',
    ]:
        if not path:
            continue
        out_dir = Path(path)
        out_dir.mkdir(parents=True, exist_ok=True)
        if out_dir.exists():
            if out_dir.stat().st_uid == 0:
                shutil.chown(str(out_dir), user=user_id, group=user_id)
        del path
        del out_dir

    if os.getenv("IS_ODOO_QUEUEJOB", "") == "1":
        # https://www.odoo.com/apps/modules/10.0/queue_job/
        sql = "update queue_job set state='pending' where state in ('started', 'enqueued');"
        with get_conn_autoclose() as cr:
            cr.execute(sql)

def get_odoo_bin(for_shell=False):
    if is_odoo_cronjob and not config.get('RUN_ODOO_CRONJOBS') == '1':
        print("Cronjobs shall not run. Good-bye!")
        sys.exit(0)

    if is_odoo_queuejob and not config.get("RUN_ODOO_QUEUEJOBS") == "1":
        print("Queue-Jobs shall not run. Good-bye!")
        sys.exit(0)

    EXEC = "odoo-bin"
    if is_odoo_cronjob:
        print('Starting odoo cronjobs')
        CONFIG = "config_cronjob"
        if version <= 9.0:
            EXEC = "openerp-server"

    elif is_odoo_queuejob:
        print('Starting odoo queuejobs')
        CONFIG = 'config_queuejob'

    else:
        CONFIG = 'config_webserver'
        if version <= 9.0:
            if for_shell:
                EXEC = "openerp-server"
            else:
                EXEC = "openerp-server"
        else:
            try:
                if config.get("ODOO_GEVENT_MODE", "") == "1":
                    raise Exception("Dont use GEVENT MODE anymore")
            except KeyError:
                pass

    EXEC = "{}/{}".format(
        os.environ["SERVER_DIR"],
        EXEC
    )

    return EXEC, CONFIG

def kill_odoo():
    if pidfile.exists():
        print("Killing Odoo")
        pid = pidfile.read_text()
        cmd = [
            '/bin/kill',
            '-9',
            pid
        ]
        if os.getenv("USE_DOCKER", "") == "1" and os.getenv("DOCKER_MACHINE", "") == "1":
            cmd = [
                '/usr/bin/sudo',
            ] + cmd
        subprocess.call(cmd)
        try:
            pidfile.unlink()
        except FileNotFoundError:
            pass
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

def __python_exe(remote_debug=False, wait_for_remote=False):
    if version <= 10.0:
        return ["/usr/bin/python"]
    else:
        # return "/usr/bin/python3"
        cmd = [
            "python3",
        ]
        if remote_debug:
            cmd += [
                '-mdebugpy',
                '--listen',
                '0.0.0.0:5678',
            ]

        if wait_for_remote:
            cmd += [
                '--wait-for-client',
            ]
        return cmd

def exec_odoo(CONFIG, *args, odoo_shell=False, touch_url=False, on_done=None,
              stdin=None, dokill=True, remote_debug=False, wait_for_remote=False, **kwargs): # NOQA
    assert not [x for x in args if '--pidfile' in x], "Not custom pidfile allowed"


    if dokill:
        kill_odoo()

    EXEC, _CONFIG = get_odoo_bin(for_shell=odoo_shell)
    CONFIG = get_config_file(CONFIG or _CONFIG)
    cmd = []
    if os.getenv("ODOO_SUDO_CMD") == "1":
        cmd = [
            "/usr/bin/sudo",
            "-E",
            "-H",
            "-u",
            ODOO_USER,
        ]
    cmd += __python_exe(remote_debug=remote_debug, wait_for_remote=wait_for_remote) + [
        EXEC,
    ]
    if odoo_shell:
        cmd += ['shell']
    try:
        DBNAME = config['DBNAME']
    except KeyError:
        DBNAME = os.environ['DBNAME']
    cmd += [
        '-c',
        CONFIG,
        '-d',
        DBNAME
    ]
    # print(Path(CONFIG).read_text())
    if not odoo_shell:
        cmd += [
            '--pidfile={}'.format(pidfile),
        ]
    cmd += args

    cmd = " ".join(map(lambda x: '"{}"'.format(x), cmd))

    def toucher():
        while True:
            try:
                r = requests.get('http://{}:'.format(
                    'localhost',
                    os.environ['INTERNAL_ODOO_PORT']
                ))
                r.raise_for_status()
            except Exception:
                raise
            else:
                print("HTTP Get to odoo succeeded.")
                break
            finally:
                time.sleep(2)

    if touch_url:
        t = threading.Thread(target=toucher)
        t.daemon = True
        print("Touching odoo url to start it")
        t.start()

    filename = Path(tempfile.mktemp(suffix='.exitcode'))
    cmd += f' || echo $? > {filename}'

    if stdin:
        cmd = f'{stdin} |' + cmd

    os.system(cmd)
    if pidfile.exists():
        pidfile.unlink()
    if on_done:
        on_done()

    rc = 0
    if filename.exists():
        try:
            rc = int(filename.read_text().strip())
        except ValueError:
            rc = -1 # undefined return code
        finally:
            filename.unlink()
    return rc
