#!/bin/bash
set -x
touch /tmp/debugging

cd /opt/src


# install marcvim
cp ~/.bashrc /tmp
cd /tmp
VIM=marcvim_installer_ubuntu-16.04.sh
if [[ ! -f $VIM ]]; then
    apt-get install -y libruby wget
    wget http://vim.itewimmer.de/$VIM
    chmod a+x $VIM
    ./$VIM
fi
pkill -9 -f vimupdate
cp /tmp/.bashrc /root

pkill -9 -f ariconnector

echo "Starting ARI Connector...."
cd /opt/src/asterisk_ari/connector
python ariconnector.py \
    --debug \
    --odoo-host $ODOO_HOST \
    --odoo-port $ODOO_PORT \
    --odoo-user $ODOO_USER \
    --odoo-password $ODOO_PASSWORD \
    --odoo-db $ODOO_DB
