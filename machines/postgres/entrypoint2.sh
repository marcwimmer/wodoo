#!/bin/bash
set -e
set +x

echo "Executing postgres entrypoint2.sh"
echo "DBNAME: $DBNAME"
export POSTGRES_DB=$DBNAME

if [[ -z "$PGDATA" ]]; then
    echo "Please define pgdata"
    exit -1
fi

if [[ "$INIT" != "1" ]]; then
    FILE=postgresql2.conf
	if [[ -n "$PGDATA" && -d "$PGDATA" ]]; then
		cp /opt/postgres.conf.d/$FILE $PGDATA/$FILE
		grep -q "include.*$FILE" $PGDATA/postgresql.conf || {
			echo "include '$FILE'" >> $PGDATA/postgresql.conf
		}
	fi
else
    echo "Init set"

    rm -Rf $PGDATA/* || true
    ASPOSTGRES="gosu postgres"
    $ASPOSTGRES /docker-entrypoint.sh postgres | grep -m 1 "database system is ready to accept connections"
    $ASPOSTGRES psql template1 -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PWD' superuser;" 
    $ASPOSTGRES psql template1 -c "CREATE DATABASE $DBNAME;"
    $ASPOSTGRES psql template1 -c "ALTER DATABASE $DBNAME OWNER TO $DB_USER"
    $ASPOSTGRES pg_ctl -D "$PGDATA" -m fast -w stop
    exit 0
fi

echo 'Normal postgres start...'
/docker-entrypoint.sh postgres
