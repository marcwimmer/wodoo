#!/bin/bash
MODULE=$1
set -x
source /env.sh
/set_permissions.sh


if [[ -n "$MODULE" ]]; then
    echo "updating just $MODULE"
else
    echo "Getting list of custom modules"
    MODULE=$(/opt/openerp/admin/update_custom_modules.py $CUSTOMS)
fi

touch /tmp/debugging
/opt/openerp/admin/oekill || {
    echo 'could not terminate odoo'
}

echo "Updating modules $MODULE..."
time sudo -H -u odoo /opt/openerp/versions/server/openerp-server \
    -c /home/odoo/config_openerp \
    -d $DBNAME \
    -u $MODULE \
    --stop-after-init \
    --log-level=debug || echo 'odoo update executed'
echo "Update of odoo done"
exit 0
