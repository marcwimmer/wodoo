#!/bin/bash
echo "Debugging in Port 9000"
/sync_source.sh
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME -c /home/odoo/config_debug --xmlrpc-port=9000 --longpolling-port=9001
