#!/bin/bash

cd /
python3<<EOF
import sys
sys.path.append('/')
import utils
with open("/tmp/odooenv.sh", 'w') as f:
    f.write("#/bin/bash\n")
    for key, value in utils.get_env().items():
        f.write('export {}={}\n'.format(key, value))
EOF
chmod a+x /tmp/odooenv.sh
source /tmp/odooenv.sh
