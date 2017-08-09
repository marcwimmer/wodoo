#!/bin/bash
set -e
set +x

RESTOREFILE=/opt/restore/$DBNAME.gz

if [ "$(id -u)" = '0' ]; then

	exec gosu postgres "$BASH_SOURCE" "$@" #restart self (like they do in entry point)

else
	echo "Restoring database $DBNAME"

	echo "try postgres-format or custom gzipped format"
	pg_ctl -w start

	tmppipe=$(mktemp -u)
	mkfifo "$tmppipe"
	gunzip -c  $RESTOREFILE > $tmppipe &
	psql $DBNAME < $tmppipe

	echo "Restoring snapshot done!"
	pg_ctl -w stop
fi
