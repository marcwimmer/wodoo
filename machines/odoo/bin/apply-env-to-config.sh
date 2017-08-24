#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

if [[ -z "$DB_HOST" || -z "$DB_USER" ]]; then
    echo "Please define all DB Env Variables!"
    exit -1
fi


cd $ADMIN_DIR/module_tools
ADDONS_PATHS=$(python <<EOF
import odoo_config
paths = odoo_config.get_odoo_addons_paths()
print ','.join(paths)
EOF
)
ADDONS_PATHS=$ADDONS_PATHS,$ADDONS_CUSTOMS


cd /home/odoo
ls config_* | while read f
do
    f=/home/odoo/$f
    sed -i "s|__DB_USER__|$DB_USER|g" $f
    sed -i "s|__DB_PWD__|$DB_PWD|g" $f
    sed -i "s|__DB_MAXCONN__|$DB_MAXCONN|g" $f
    sed -i "s|__DB_PORT__|$DB_PORT|g" $f
    sed -i "s|__DB_HOST__|$DB_HOST|g" $f
    sed -i "s|__DB_HOST__|$DB_HOST|g" $f
    sed -i "s|__ADDONS_PATH__|$ADDONS_PATHS|g" $f
done
