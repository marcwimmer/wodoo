#!/bin/bash
touch /tmp/debugging

# install marcvim
pkill -9 -f openerp || true
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME --log-level=error --xmlrpc-port=8072
