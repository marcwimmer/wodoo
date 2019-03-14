#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

# sync source is done by extra machine

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
if [[ "$ENDLESS_LOOP" == "1" ]]; then
	while true;
	do
		sleep 100
	done
    exit 0
fi

set -x
if [[ "$IS_ODOO_CRONJOB" == "1" ]]; then
    echo 'Starting odoo cronjobs'
    CONFIG=config_openerp
    EXEC="$ODOO_EXECUTABLE_CRONJOBS"
else
    echo 'Starting odoo gevent'
    CONFIG=config_gevent
    EXEC="$ODOO_EXECUTABLE_GEVENT"
fi
sudo -E -H -u "$ODOO_USER" $SERVER_DIR/$EXEC -c "$CONFIG_DIR/$CONFIG"  -d "$DBNAME" --log-level="$ODOO_LOG_LEVEL"
