#!/bin/bash
set -x
set -e
CONFIG="$(sed 's/^/-c/' /config)"

cp /tmp/docker-entrypoint-initdb.d/* /docker-entrypoint-initdb.d || true
chown -R postgres:postgres /docker-entrypoint-initdb.d  || true
chmod a+x /docker-entrypoint-initdb.d/*.sh || true
exec gosu postgres /docker-entrypoint.sh postgres $CONFIG
