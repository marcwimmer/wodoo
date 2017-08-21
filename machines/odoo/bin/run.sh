#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set +x

# sync source is done by extra machine

/apply-env-to-config.sh

echo "Executing autosetup..."
/run_autosetup.sh
echo "Done autosetup"

# abort start, if traces are found
cd /opt/odoo/active_customs
/opt/odoo/admin/find-traces && {
    echo "traces found - start aborted"
    exit 1
}

echo "Starting up odoo"
if [[ "$IS_ODOO_CRONJOB" == "1" ]]; then
    echo 'Starting odoo cronjobs'
    sudo -E -H -u odoo /opt/odoo/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=$LOGLEVEL
else
    echo 'Starting odoo gevent'
    sudo -E -H -u odoo /opt/odoo/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=$LOGLEVEL
fi
