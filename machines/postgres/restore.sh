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

    # determine restore method 
    method=pg_restore
    needs_unzip=1
    gunzip -c "$RESTOREFILE" | head | grep -q PostgreSQL.database.dump && {
        method=psql
    }
    head "$RESTOREFILE" | grep -q PostgreSQL.database.dump && {
        needs_unzip=0
        method=psql
    }

    if [[ "$needs_unzip" == "1" ]]; then
        tmppipe=$(mktemp -u)
        mkfifo "$tmppipe"
        gunzip -c  "$RESTOREFILE" > "$tmppipe" &
    else
        tmppipe="$RESTOREFILE"
    fi
	echo "Restoring using $method..."
	$method -d "$DBNAME" < "$tmppipe"

	echo "Restoring snapshot done!"
	pg_ctl -w stop
fi
