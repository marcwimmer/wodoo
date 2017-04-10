#!/bin/bash
echo "Debugging in Port $DEBUG_PORT_ODOO"
/sync_source.sh

echo "Executing autosetup..."
/run_autosetup.sh $ODOO_PROD
echo "Done autosetup"

sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME -c /home/odoo/config_debug --xmlrpc-port=$DEBUG_PORT_ODOO --longpolling-port=$DEBUG_PORT_ODOO_LONGPOLLING
