#!/bin/bash
set -e
set +x

if [ "$(id -u)" = '0' ]; then
	exec gosu postgres "$BASH_SOURCE" "$@" #restart self (like they do in entry point)
else:
	pg_dump -Z0 -Fc $DBNAME | pigz --rsyncable > /opt/dumps/$DBNAME.gz
fi
