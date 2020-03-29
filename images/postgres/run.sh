#!/bin/bash
set -xe
CONFIG="$(sed 's/^/-c/' /config)"

# volume mount safe (if odoo is mounted into virtual box)
cp /tmp/docker-entrypoint-initdb.d/* /docker-entrypoint-initdb.d
chown -R postgres:postgres /docker-entrypoint-initdb.d 
exec gosu postgres /docker-entrypoint.sh postgres $CONFIG
