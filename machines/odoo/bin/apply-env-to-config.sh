#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$DB_HOST" || -z "$DB_USER" ]]; then
    echo "Please define all DB Env Variables!"
    exit -1
fi

declare -a FILES=("config_openerp" "config_gevent" "config_debug" "config_shell")
for f in ${FILES[@]};
do
    f=/home/odoo/$f
    sed -i "s|__DB_USER__|$DB_USER|g" $f
    sed -i "s|__DB_PWD__|$DB_PWD|g" $f
    sed -i "s|__DB_MAXCONN__|$DB_MAXCONN|g" $f
    sed -i "s|__DB_PORT__|$DB_PORT|g" $f
    sed -i "s|__DB_HOST__|$DB_HOST|g" $f
done
