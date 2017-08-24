#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
if [[ -z "$1" ]]; then
    echo "Missing test-file"
    exit -1
fi

if [[ -z "$2" ]]; then
    echo "Missing module name"
    exit -1
fi
/sync_source.sh
/apply-env-to-config.sh

echo "Executing autosetup..."
/run_autosetup.sh
echo "Done autosetup"

module=$2
sudo -E -H -u odoo /opt/odoo/server/openerp-server \
    -d $DBNAME \
    -c /home/odoo/config_unittest \
	-u $module
    --pidfile=$DEBUGGER_ODOO_PID \
    --stop-after-init \
    --test-file=$1 \
    --test-report-directory=/tmp \
    --log-level=debug
