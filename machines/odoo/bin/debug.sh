#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

echo "$*" |grep -q '[-]quick' || {
	echo "Executing autosetup..."
	/run_autosetup.py
	echo "Done autosetup"
}

# for module queue_job
export TEST_QUEUE_JOB_NO_DELAY=1  

sudo pkill -9 -f /opt/odoo > /dev/null
ODOO_TRACE=1 sudo -E -H -u "$ODOO_USER" "$SERVER_DIR/$ODOO_EXECUTABLE_DEBUG" -d $DBNAME -c "$CONFIG_DIR/config_debug" --pidfile="$DEBUGGER_ODOO_PID"
