#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
if [[ -z "$1" ]]; then
    echo "Missing test-file"
    exit -1
fi

reset
/apply-env-to-config.sh

path=$ADDONS_CUSTOMS/$module/tests/$(basename $1)

sudo -E -H -u $ODOO_USER $SERVER_DIR/openerp-server \
    -d $DBNAME \
    -c $CONFIG_DIR/config_unittest \
    --pidfile=$DEBUGGER_ODOO_PID \
    --stop-after-init \
    --test-file=$path \
    --test-report-directory=/tmp \
    --log-level=debug
