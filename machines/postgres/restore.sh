#!/bin/bash

echo "Restoring database $DBNAME"
/docker-entrypoint.sh postgres &
sleep 5
dropdb $DBNAME || echo 'database did not exist'
createdb $DBNAME

# try postgres-format or custom gzipped format
pg_restore -d $DBNAME /opt/restore/$DBNAME.gz || {
    gunzip -c /opt/restore/$DBNAME.gz | psql $DBNAME
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
