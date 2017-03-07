#!/bin/bash
set -ex

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

mkdir -p /opt/openerp
echo "rsyncing odoo source"
time rsync /opt/src/admin/ /opt/openerp/admin -ar --delete --exclude=.git

source /env.sh
source /opt/openerp/admin/setup_bash

# Setting up productive odoo
echo Starting odoo for customs $CUSTOMS

echo "Odoo version is $ODOO_VERSION"

echo "Syncing odoo to executable dir"
while true;
do
    rsync /opt/src/customs/$CUSTOMS/ /opt/openerp/active_customs -arP --delete --exclude=.git && break
    sleep 1
    echo 'error at rsync - retrying'
done
mkdir -p /opt/openerp/versions
mkdir -p /opt/openerp/customs
chmod a+x /opt/openerp/admin/*.sh

echo "Applying patches"
/opt/openerp/admin/apply_patches.sh

echo "oeln"
/opt/openerp/admin/oeln $CUSTOMS

rm -Rf /opt/openerp/versions || true
mkdir -p /opt/openerp/versions
ln -s /opt/openerp/active_customs/odoo /opt/openerp/versions/server

# use virtualenv installed packages for odoo

/set_permissions.sh
