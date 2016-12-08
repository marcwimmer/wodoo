#!/bin/bash
source /env.sh

if [[ -n "$MODULE" ]]; then
    echo "updating just $MODULE"
    MODULE=$(/opt/openerp/admin/update_custom_modules.py)
else
    echo "Getting list of custom modules"
fi


echo "Updating modules $MODULE..."
time sudo -H -u odoo /opt/openerp/versions/server/openerp-server \
    -c /home/odoo/config_openerp
    -d $DBNAME \
    -u $MODULE \
    --stop-after-init \
    --log-level=debug || echo 'odoo update executed'
echo "Update of odoo done"
exit 0
