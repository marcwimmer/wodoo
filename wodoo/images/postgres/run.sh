#!/bin/bash
set -e

python3 <<EOF
print("Version 1.0")
import os
with open('/config') as file:
    conf = file.read().split("\n")
conf += os.getenv('POSTGRES_CONFIG').split(",")
conf = list(filter(lambda x: bool((x or '').strip()), conf))

print("Applying configuration:\n" + '\n'.join(conf))

conf = list(map(lambda x: f"-c {x}", conf))

with open('/start.sh', 'w') as f:
    f.write('/usr/local/bin/docker-entrypoint.sh postgres ' + ' '.join(conf))

EOF

if [[ "$1" == "postgres" ]]; then
    exec gosu postgres bash /start.sh
else
    exec gosu postgres "$@"
fi
