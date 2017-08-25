#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
if [[ -z "$1" ]]; then
    echo "Missing test-file"
    exit -1
fi

reset
/apply-env-to-config.sh

cd $ADMIN_DIR/module_tools
module=$(python -c "import module_tools; print module_tools.get_module_of_file('$1')")
path=$ADDONS_CUSTOMS/$module/tests/$(basename $1)

sudo -E -H -u $ODOO_USER $SERVER_DIR/openerp-server \
    -d $DBNAME \
    -c $CONFIG_DIR/config_unittest \
	-u $module \
    --pidfile=$DEBUGGER_ODOO_PID \
    --stop-after-init \
    --test-file=$path \
    --test-report-directory=/tmp \
    --log-level=debug
