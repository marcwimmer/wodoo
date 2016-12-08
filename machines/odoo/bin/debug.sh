#!/bin/bash
touch /tmp/debugging

# install marcvim
pkill -9 -f openerp || true
sudo -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME --log-level=error
