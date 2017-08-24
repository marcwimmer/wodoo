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
/apply-env-to-config.sh
/patch_odoo.sh
$ADMIN_DIR/link_modules
/run_autosetup.sh

module=$2
sudo -E -H -u $ODOO_USER $SERVER_DIR/openerp-server \
    -d $DBNAME \
    -c $CONFIG_DIR/config_unittest \
	-u $module
    --pidfile=$DEBUGGER_ODOO_PID \
    --stop-after-init \
    --test-file=$1 \
    --test-report-directory=/tmp \
    --log-level=debug
