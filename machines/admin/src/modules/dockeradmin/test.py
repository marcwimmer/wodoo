#import docker
import subprocess
import json
#client = docker.from_env(assert_hostname='172.18.0.1')
#print [x for x in client.containers.list()]

containers = json.loads(subprocess.check_output(['/usr/bin/curl', '--unix-socket', '/var/run/docker.sock', 'http:/containers/json']))

print containers[0]['Names']

