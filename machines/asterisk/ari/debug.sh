#!/bin/bash
set -x

cd /opt/src

apt-get install -y libruby wget

# install marcvim
cd /tmp
VIM=marcvim_installer_ubuntu-16.04.sh
if [[ ! -f $VIM ]]; then
    wget http://vim.itewimmer.de/$VIM
    chmod a+x $VIM
    ./$VIM
fi

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
