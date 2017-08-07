#!/bin/bash
if [[ -z "$1" ]]; then
    echo "Missing test-file"
    exit -1
fi

/sync_source.sh
/apply-env-to-config.sh

echo "Executing autosetup..."
/run_autosetup.sh
echo "Done autosetup"


sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server \
    -d $DBNAME \
    -c /home/odoo/config_debug \
    --pidfile=$DEBUGGER_ODOO_PID \
    --stop-after-init \
    --test-file=$1 \
    --test-report-directory=/tmp \
    --log-level=debug
