#!/bin/bash
pgrep -f nginx || /usr/sbin/nginx
set -x

echo "Starting ARI Connector...."
cd /opt/odoo/active_customs/common/asterisk_ari/connector

python ariconnector.py \
    --debug \
    --odoo-host $ODOO_HOST \
    --odoo-port $ODOO_PORT \
    --odoo-user $ODOO_USER \
    --odoo-password $ODOO_PASSWORD \
    --odoo-db $ODOO_DB
