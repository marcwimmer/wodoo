#!/bin/bash
set -e
cd /opt
[ -d asterisk_ari ] && rm -Rf /opt/asterisk_ari
git clone --depth 1 --branch deploy git.mt-software.de:/git/openerp/modules/asterisk_ari
ifconfig
WAIT=20

ifconfig
echo Waiting $WAIT seconds to start ari...
sleep $WAIT
cd /opt/asterisk_ari/connector
python ariconnector.py \
    --username-asterisk $USERNAME_ASTERISK \
    --password-asterisk $PASSWORD_ASTERISK \
    --host-asterisk $HOST_ASTERISK \
    --port-asterisk $PORT_ASTERISK \
    --odoo-host $ODOO_HOST \
    --odoo-port $ODOO_PORT \
    --odoo-userid $ODOO_USER_ID \
    --odoo-password $ODOO_PASSWORD \
    --odoo-db $ODOO_DB
