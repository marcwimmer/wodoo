#!/bin/bash
set -e

if [[ "$RUN_ASTERISK" == "0" ]]; then
    echo "asterisk is turned off by customs.env - good bye! :)"
    exit 0
fi

cd /opt
if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    rm /opt/asterisk_ari/ -Rf || true
    git clone --depth 1 --branch deploy git.mt-software.de:/git/openerp/modules/asterisk_ari
    echo 'done updating ari'
    exit 0
fi

echo "Waiting for asterisk to arrive at port $PORT_ASTERISK"
while true; do
    if $(nc -z $HOST_ASTERISK $PORT_ASTERISK); then
        break
    fi
    sleep 1
done
echo "Asterisk arrived! connecting..."

echo "Waiting for odoo to arrive at port $ODOO_PORT"
while true; do
    if $(nc -z $ODOO_HOST $ODOO_PORT); then
        break
    fi
    sleep 1
done
echo "Odoo arrived! connecting..."

echo "Starting ARI Connector...."
cd /opt/asterisk_ari/connector
python ariconnector.py \
    --username-asterisk $USERNAME_ASTERISK \
    --password-asterisk $PASSWORD_ASTERISK \
    --host-asterisk $HOST_ASTERISK \
    --port-asterisk $PORT_ASTERISK \
    --odoo-host $ODOO_HOST \
    --odoo-port $ODOO_PORT \
    --odoo-user $ODOO_USER \
    --odoo-password $ODOO_PASSWORD \
    --odoo-db $ODOO_DB
