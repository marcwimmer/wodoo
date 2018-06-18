#!/usr/bin/python
import os
import subprocess
import inspect
import time
import sys
from threading import Thread

FNULL = open(os.devnull, 'w')
PID_FILE = "$TMPDIR/$DC_PREFIX_sync_source.pid"
remote_loc = "rsync://127.0.0.1:10874/odoo/"
exclude = ["--exclude=.git"]
ODOO_BASE = os.path.dirname(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))) # script directory
if os.path.islink(ODOO_BASE):
    ODOO_BASE = os.path.normpath(os.readlink(ODOO_BASE))

def ensure_once():
    if os.path.exists(PID_FILE):
        print("Killing existing fswatchsync")
        proc = subprocess.Popen(['pkill', '-F', PID_FILE], stdout=FNULL)
        proc.wait()
        if not proc.returncode:
            print("Successfully killed")
            os.unlink(PID_FILE)
        else:
            print("Error killing current process")
            sys.exit(2)
        with open(PID_FILE, 'w') as f:
            f.write(os.getpid())


CUSTOMS = sys.argv[1] if len(sys.argv) > 0 else None
if not CUSTOMS:
    print("Please provide customs as parameter1")
    sys.exit(1)

CUSTOMS_DIR = os.path.join(ODOO_BASE, 'data/src/customs', CUSTOMS) + "/"

def complete_sync():
    env2 = os.environ.copy()
    env2["NO_SYNC"] = "1"
    proc = subprocess.Popen(["./odoo", "up", '-m', "odoo_source_syncer"], cwd=ODOO_BASE, env=env2)
    print("Initial complete sync of sources")

    while True:
        try:
            print CUSTOMS_DIR, remote_loc
            subprocess.check_call([
                'rsync',
                CUSTOMS_DIR,
                remote_loc,
                "-ar",
            ] + exclude + [
                "--delete-after"
            ], cwd=CUSTOMS_DIR)
            break
        except Exception:
            time.sleep(3)

    proc.kill()


def watch_fs():
    os.system('reset')
    print("Watching directory {} for changes".format(CUSTOMS_DIR))

    # copy file at once (first rsync); delete deleted files later in background
    proc = subprocess.Popen([
        "fswatch",
        "-l", " 0.1",
        "-e", ".git/",
        "-e", " .pyc",
        CUSTOMS_DIR
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1)

    def reader(pipe):
        with pipe:
            for abs_filepath in iter(pipe.readline, ''):
                while True:
                    try:
                        abs_filepath = abs_filepath.strip()
                        rel_path = abs_filepath.replace(CUSTOMS_DIR, '')
                        destination = remote_loc + rel_path
                        if os.path.exists(abs_filepath):
                            subprocess.check_call([
                                'rsync',
                                '--quiet',
                                '--relative',
                                '-avz',
                            ] + exclude + [
                                abs_filepath,
                                destination
                            ])

                        # sync dir of deleted files
                        source = os.path.dirname(abs_filepath) + "/"
                        destination = os.path.dirname(destination) + "/"
                        subprocess.check_call([
                            'rsync',
                            '--delete-after',
                            '--quiet',
                            '--relative',
                            '-avz',
                        ] + exclude + [
                            source,
                            destination
                        ])

                    except Exception:
                        time.sleep(1)
                    else:
                        break

    t = Thread(target=reader, args=[proc.stdout])
    t.daemon = True
    t.start()
    proc.wait()


if __name__ == '__main__':
    #ensure_once()
    #complete_sync()
    watch_fs()
