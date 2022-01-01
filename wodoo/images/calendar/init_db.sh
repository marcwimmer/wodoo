#!/bin/bash
while true; do
    if $(nc -z $DBHOST $DBPORT); then
        break
    fi
    sleep 1
done

if psql -h $DBHOST -U $AWL_DBAUSER -lqt | cut -d \| -f 1 | grep -qw $AWL_DBNAME; then
	echo 'database already exists'
else 
	echo 'creating database'
	cd /opt/src
	./davical/dba/create-database.sh $AWL_DBNAME "$INITIAL_ADMIN_PASSWORD"
fi
