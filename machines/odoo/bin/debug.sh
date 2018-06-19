#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
source /eval_odoo_settings.sh

echo "$*" |grep -q '[-]quick' || {
	/apply-env-to-config.sh

	echo "Executing autosetup..."
	/run_autosetup.sh
	echo "Done autosetup"
}

sudo pkill -9 -f /opt/odoo > /dev/null
ODOO_TRACE=1 sudo -E -H -u "$ODOO_USER" "$SERVER_DIR/$ODOO_EXECUTABLE" -d $DBNAME -c "$CONFIG_DIR/config_debug" --pidfile="$DEBUGGER_ODOO_PID"
