#!/bin/bash
touch /tmp/debugging
pkill -9 -f openerp-server || true
sudo -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME --log-level=error
