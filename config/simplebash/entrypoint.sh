#!/bin/bash
set +x

echo "$DB_HOST:$DB_PORT:$DBNAME:$DB_USER:$DB_PWD" > ~/.pgpass
echo "$DB_HOST:$DB_PORT:template1:$DB_USER:$DB_PWD" >> ~/.pgpass
chmod 600 ~/.pgpass

exec "$@"
