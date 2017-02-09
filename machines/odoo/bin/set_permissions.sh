#!/bin/bash
set -x
echo "setting ownership of /opt/oefiles to odoo"
chown odoo:odoo /opt/oefiles -R
echo "setting ownership of /opt/openerp to odoo"
chown odoo:odoo /opt/openerp/ -R
echo "setting ownership of $CUPS_TOPRINT to odoo"
chown odoo:odoo $CUPS_TOPRINT -R


if [[ -z "$DB_HOST" ]]; then
    echo "Please define all DB Env Variables!"
    exit -1
fi

declare -a FILES=("config_openerp" "config_gevent" "config_debug")
for f in ${FILES[@]};
do
    f=/home/odoo/$f
    sed -i "s|__DB_USER__|$DB_USER|g" $f
    sed -i "s|__DB_PWD__|$DB_PWD|g" $f
    sed -i "s|__DB_MAXCONN__|$DB_MAXCONN|g" $f
    sed -i "s|__DB_PORT__|$DB_PORT|g" $f
    sed -i "s|__DB_HOST__|$DB_HOST|g" $f
    cat $f
done
