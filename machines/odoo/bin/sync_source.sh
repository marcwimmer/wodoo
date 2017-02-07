#!/bin/bash
set -ex

rsync /opt/src/admin/ /opt/openerp/admin -arP --delete --exclude=.git

source /env.sh
source /opt/openerp/admin/setup_bash

# Setting up productive odoo
echo Starting odoo for customs $CUSTOMS

/set_permissions.sh
echo "Odoo version is $ODOO_VERSION"

echo "Syncing odoo to executable dir"
rsync /opt/src/customs/$CUSTOMS/ /opt/openerp/active_customs -arP --delete --exclude=.git
mkdir -p /opt/openerp/versions
mkdir -p /opt/openerp/customs
chown odoo:odoo /opt/openerp/versions -R
chown odoo:odoo /opt/openerp/customs -R
chmod a+x /opt/openerp/admin/*.sh

echo "Applying patches"
/opt/openerp/admin/apply_patches.sh

echo "oeln"
/opt/openerp/admin/oeln $CUSTOMS

rm -Rf /opt/openerp/versions || true
mkdir -p /opt/openerp/versions
ln -s /opt/openerp/active_customs/odoo /opt/openerp/versions/server

# use virtualenv installed packages for odoo

echo "Executing autosetup..."
/run_autosetup.sh $ODOO_PROD
echo "Done autosetup"
