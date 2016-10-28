#!/bin/bash
touch /tmp/debugging
pkill -9 -f openerp || true
sudo -H -u odoo /opt/openerp/versions/server/openerp-gevent -d $DBNAME --log-level=debug
