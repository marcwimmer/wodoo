import os
import subprocess
import time
import humanize
import sys
from threading import Thread
from Queue import Queue

def __find_files(cwd, *options):
    """
    :param options: ["-name", "default.settings"]
    """
    files = subprocess.check_output(["find"] + list(options), cwd=cwd)
    files = files.split("\n")
    files = [x for x in files if x and not x.endswith('/.')]
    files = [os.path.normpath(os.path.join(cwd, x)) for x in files]
    return files


def __system(cmd, cwd=None, suppress_out=False, raise_exception=True,
             wait_finished=True, shell=False, logger=None, stdin=None,
             pipeout=None, redirect_std_out_to_file=None,
             progress=False, progress_every_seconds=1,
             ):
    assert isinstance(cmd, list)

    STDPIPE, ERRPIPE, bufsize = subprocess.PIPE, subprocess.PIPE, 1
    if (not wait_finished and pipeout is None) or pipeout is False:
        STDPIPE, ERRPIPE, bufsize = None, None, -1
    if pipeout:
        bufsize = 4096
        suppress_out = True
    proc = subprocess.Popen(cmd, shell=shell, stdout=STDPIPE, stderr=ERRPIPE, bufsize=bufsize, cwd=cwd, stdin=stdin)
    collected_errors = []

    def reader(pipe, q):
        try:
            with pipe:
                for line in iter(pipe.readline, ''):
                    q.put((pipe, line))
        except Exception as e:
            print e
        finally:
            q.put(None)

    data = {
        'size_written': 0,
    }
    size_written = out_file = 0
    if redirect_std_out_to_file:
        out_file = open(redirect_std_out_to_file, 'w')
    out = []

    def heartbeat():
        while proc.returncode is None:
            time.sleep(progress_every_seconds)
            print("{} processed".format(humanize.naturalsize(data['size_written'])))

    def handle_output():
        try:
            err = proc.stderr
            q = Queue()
            Thread(target=reader, args=[proc.stdout, q]).start()
            Thread(target=reader, args=[proc.stderr, q]).start()
            for source, line in iter(q.get, None):
                if source != err:
                    out.append(line)
                else:
                    collected_errors.append(line.strip())
                if source == err or not suppress_out:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                if source != err:
                    data['size_written'] += len(line)
                if redirect_std_out_to_file:
                    if source != err:
                        out_file.write(line)

                if logger:
                    if source == err:
                        logger.error(line.strip())
                    else:
                        logger.info(line.strip())
        except Exception as e:
            print e
    if progress:
        t = Thread(target=heartbeat)
        t.daemonized = True
        t.start()

    if wait_finished or progress or redirect_std_out_to_file:
        t = Thread(target=handle_output)
        t.daemonized = True
        t.start()
        if wait_finished:
            t.join()

    if not wait_finished:
        return proc
    proc.wait()
    if out_file:
        out_file.close()
        print("{} Size: {}".format(redirect_std_out_to_file, humanize.naturalsize(size_written)))

    if proc.returncode and raise_exception:
        print '\n'.join(collected_errors)
        raise Exception("Error executing: {}".format(" ".join(cmd)))
    return "".join(out)

def __safe_filename(name):
    name = name or ''
    for c in [':\\/+?*;\'" ']:
        name = name.replace(c, "_")
    return name

def __write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def __append_line(path, line):
    if not os.path.exists(path):
        content = ""
    else:
        with open(path, 'r') as f:
            content = f.read().strip()
    content += "\n" + line
    with open(path, 'w') as f:
        f.write(content)

def __read_file(path, error=True):
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception:
        if not error:
            return""
