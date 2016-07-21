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

if [[ -n "$DO_BACKUP" ]]; then
    /docker-entrypoint.sh postgres &
    sleep 10
    pg_dump $DBNAME|gzip > /opt/dumps/$DBNAME_$(date).gz
    pkill postgres
else
    if [[ -n "$RESTORE_DUMP" ]]; then 
        echo "Restoring database $DBNAME"
        /docker-entrypoint.sh postgres &
        sleep 5
        dropdb $DBNAME || echo 'database did not exist'
        createdb $DBNAME
        pg_restore -d $DBNAME /opt/dumps/$DBNAME.gz || {
            gunzip -c /opt/dumps/$DBNAME.gz | psql $DBNAME
        }
        psql template1 -c "alter database $DBNAME owner to odoo;"
        echo "Restoring snapshot done!"
        pkill -f postgres
        echo "waiting for postgres to stop"
        while true; do
            if [[ -n "$(pgrep postgres)" ]]; then
                sleep 1
                echo "waiting for postgres to stop another second"
            else
                break
            fi
        done
    else
        echo 'Normal postgres start...'
        /docker-entrypoint.sh postgres
    fi
fi
