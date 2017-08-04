#!/bin/bash
set -e
set +x

echo "Executing postgres entrypoint2.sh"
echo "DBNAME: $DBNAME"

if [[ -z "$PGDATA" ]]; then
    echo "Please define pgdata"
    exit -1
fi

if [[ -n "$INIT" ]]; then
    FILE=postgresql2.conf
    cp /opt/postgres.conf.d/$FILE $PGDATA/$FILE
    grep -q "include.*$FILE" $PGDATA/postgresql.conf || {
        echo "include '$FILE'" >> $PGDATA/postgresql.conf
    }
fi

echo 'Normal postgres start...'

if [[ "$INIT" == "1" ]]; then

    rm -Rf $PGDATA/* || true
    /docker-entrypoint.sh postgres | grep -m 1 "database system is ready to accept connections"


else
    /docker-entrypoint.sh postgres
fi
