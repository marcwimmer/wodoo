#!/bin/bash
set -e
CONFIG="$(sed 's/^/-c/' /config)"

if [[ "$1" == "postgres" ]]; then
    exec gosu postgres bash /usr/local/bin/docker-entrypoint.sh postgres $CONFIG
else
    exec gosu postgres "$@"
fi
