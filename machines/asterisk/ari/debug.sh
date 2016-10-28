#!/bin/bash
set -x

cd /opt/src

run apt-get install -y libruby wget

cd /tmp
wget http://vim.itewimmer.de/marcvim_installer_ubuntu-16.04.sh
chmod a+x marcvim_installer_ubuntu-16.04.sh
./marcvim_installer_ubuntu-16.04.sh
pkill -9 -f vimupdate

pkill -9 -f ariconnector

echo "Starting ARI Connector...."
cd /opt/src/asterisk_ari/connector
python ariconnector.py \
    --odoo-host $ODOO_HOST \
    --odoo-port $ODOO_PORT \
    --odoo-user $ODOO_USER \
    --odoo-password $ODOO_PASSWORD \
    --odoo-db $ODOO_DB
