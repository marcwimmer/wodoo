#!/bin/bash
set -e
set -x


source /env.sh
source /opt/openerp/admin/setup_bash

# Setting up productive odoo
echo Starting odoo for customs $CUSTOMS

/set_permissions.sh
echo "Odoo version is $ODOO_VERSION"

echo "Syncing odoo to executable dir"
rsync /opt/src/customs/$CUSTOMS/ /opt/openerp/active_customs -arP --delete --exclude=.git
rsync /opt/src/admin/ /opt/openerp/admin -arP --delete --exclude=.git
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

echo on version 6.1 start soffice
if [[ "$ODOO_VERSION" == "6.1" ]]; then
    sudo -H -u odoo /usr/bin/soffice --nologo --nofirststartwizard --headless --norestore --invisible --accept="socket,host=localhostort=8100,tcpNoDelay=1;urp;" &

fi

echo "Starting up odoo"
if [[ "$RUN_CRONJOBS" == "1" ]]; then
    sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=$LOGLEVEL &
fi
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=$LOGLEVEL &
