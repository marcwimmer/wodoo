#!/bin/bash
set -x
set -e
CONFIG="$(sed 's/^/-c/' /config)"


#exec gosu postgres /usr/local/bin/docker-entrypoint.sh postgres $CONFIG
echo "BYE"
