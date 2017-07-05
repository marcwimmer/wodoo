#!/bin/bash
set -e
set -x


/sync_source.sh

echo "Executing autosetup..."
/run_autosetup.sh
echo "Done autosetup"


echo "Starting up odoo"
if [[ "$IS_ODOO_CRONJOB" == "1" ]]; then
    echo 'Starting odoo cronjobs'
    sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=$LOGLEVEL
else
    echo 'Starting odoo gevent'
    sudo -E -H -u odoo /opt/openerp/versions/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=$LOGLEVEL
fi
