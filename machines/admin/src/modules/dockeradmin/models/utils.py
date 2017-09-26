import json
import subprocess

def get_containers():
    containers = json.loads(subprocess.check_output(['/usr/bin/curl', '--unix-socket', '/var/run/docker.sock', 'http:/containers/json']))

    return containers
