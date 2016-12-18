#!/bin/bash
set -e
set +x
cd /

echo "Executing postgres entrypoint2.sh"
echo "DBNAME: $DBNAME"

if [[ -z "$PGDATA" ]]; then
    echo "Please define pgdata"
    exit -1
fi

FILE=postgres2.conf
grep -q $PGDATA/postgresql.conf "$CONFPATH" || {
	cat "include_dir '$CONFPATH'" > $PGDATA/postgresql.conf
}



echo 'Normal postgres start...'
/docker-entrypoint.sh postgres
