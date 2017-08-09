#!/bin/bash
set -e
set +x

RESTOREFILE=/opt/restore/$1

if [ "$(id -u)" = '0' ]; then

	exec gosu postgres "$BASH_SOURCE" "$@" #restart self (like they do in entry point)

else
	echo "Restoring database $DBNAME"

	echo "try postgres-format or custom gzipped format"
	pg_ctl -w start

	tmppipe=$(mktemp -u)
	mkfifo "$tmppipe"
	gunzip -c  $RESTOREFILE > $tmppipe &
	pg_restore -d $DBNAME < $tmppipe

	echo "Restoring snapshot done!"
	pg_ctl -w stop
fi
