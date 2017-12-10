#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$RESTOREFILE" ]]; then
	echo "RESTOREFILE is missing."
	exit -1
fi

if [ "$(id -u)" = '0' ]; then

	exec gosu postgres "$BASH_SOURCE" "$@" #restart self (like they do in entry point)

else
	echo "This is the dump file size:"
	stat --printf="%s" "$RESTOREFILE"
	sleep 2

	echo "Restoring database $DBNAME"

	echo "try postgres-format or custom gzipped format"
	pg_ctl -w start

	tmppipe=$(mktemp -u)
	mkfifo "$tmppipe"
	gunzip -c  "$RESTOREFILE" > "$tmppipe" &
	echo "Restoring..."
	pg_restore -d "$DBNAME" < "$tmppipe"

	echo "Restoring snapshot done!"
	pg_ctl -w stop
fi
