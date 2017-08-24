#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

echo "$*" |grep -q '[-]quick' || {
	/apply-env-to-config.sh

	echo "Executing autosetup..."
	/run_autosetup.sh
	echo "Done autosetup"
}

sudo pkill -9 -f /opt/odoo
sudo -E -H -u odoo $SERVER_DIR/openerp-server -d $DBNAME -c $CONFIG_DIR/config_debug --pidfile=$DEBUGGER_ODOO_PID
