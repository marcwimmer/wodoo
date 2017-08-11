#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

echo "$*" |grep -q '[-]quick' || {
	/sync_source.sh
	/apply-env-to-config.sh

	echo "Executing autosetup..."
	/run_autosetup.sh
	echo "Done autosetup"
}

sudo pkill -9 -f /opt/openerp
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -d $DBNAME -c /home/odoo/config_debug --pidfile=$DEBUGGER_ODOO_PID
