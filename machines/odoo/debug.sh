#!/bin/bash
touch /tmp/debugging

# install marcvim
cd /tmp
VIM=marcvim_installer_ubuntu-16.04.sh
if [[ ! -f $VIM ]]; then
    apt-get install -y libruby wget
    wget http://vim.itewimmer.de/$VIM
    chmod a+x $VIM
    ./$VIM
fi
pkill -9 -f vimupdate


pkill -9 -f openerp || true
sudo -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME --log-level=error
