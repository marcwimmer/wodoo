#!/bin/bash
set -x
set -e

echo "Restoring database $DBNAME"
/docker-entrypoint.sh postgres &
WAIT=15
echo "Waiting $WAIT seconds for database system to come up"
sleep $WAIT
sudo -u postgres -E dropdb $DBNAME || echo 'database did not exist'

echo "Creating database $DBNAME now per command line - if fails, then retry again please"
sudo -u postgres -E createdb $DBNAME

echo "try postgres-format or custom gzipped format"
sudo -u postgres -E pg_restore -d $DBNAME /opt/restore/$DBNAME.gz || {
    gunzip -c /opt/restore/$DBNAME.gz | sudo -u postgres -E psql $DBNAME
}
sudo -u postgres -E psql template1 -c "alter database $DBNAME owner to odoo;"
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
