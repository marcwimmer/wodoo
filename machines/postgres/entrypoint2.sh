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
fi

echo 'Normal postgres start...'

if [[ "$INIT" == "1" ]]; then

	if [ "$(id -u)" = '0' ]; then
		rm -Rf $PGDATA/* || true
		/docker-entrypoint.sh postgres | grep -m 1 "database system is ready to accept connections"
		exec gosu postgres "$BASH_SOURCE" "$@"  #restart self (like they do in entry point)
	else
		psql template1 -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PWD' superuser;" 
		pg_ctl -D "$PGDATA" -m fast -w stop
	fi


else
    /docker-entrypoint.sh postgres
fi
