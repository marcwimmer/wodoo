#!/bin/bash
set -e

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
time rsync /opt/openerp/customs/$CUSTOMS/ /opt/openerp/active_customs --info=progress2  -arP --delete --exclude=.git
mkdir -p /opt/openerp/versions
mkdir -p /opt/openerp/customs
cd /opt/openerp/customs && ln -s /opt/openerp/active_customs $CUSTOMS
chmod a+x /opt/openerp/admin/*.sh

rm -Rf /opt/openerp/versions || true
mkdir -p /opt/openerp/versions
# must be rsync, so that patches apply
ln -s /opt/openerp/active_customs/odoo /opt/openerp/versions/server

echo "oeln"
/opt/openerp/admin/oeln $CUSTOMS

echo "Applying patches"
CUSTOMS=$CUSTOMS VERSION=$ODOO_VERSION CUSTOMS_DIR=/opt/openerp/active_customs SERVER_DIR=/opt/openerp/versions/server /bin/bash /opt/openerp/admin/apply_patches.sh || {
    echo "Error at applying patches! Please check output and the odoo version"
    exit -1
}

# use virtualenv installed packages for odoo

/set_permissions.sh
