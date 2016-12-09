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

echo 'Normal postgres start...'
/docker-entrypoint.sh postgres
