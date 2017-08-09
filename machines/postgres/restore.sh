#!/bin/bash
set -e
set +x

echo "Restoring database $DBNAME"

echo "try postgres-format or custom gzipped format"
gunzip -c /opt/restore/$DBNAME.gz | sudo -u postgres -E psql $DBNAME

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
