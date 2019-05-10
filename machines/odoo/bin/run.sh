#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

# sync source is done by extra machine

echo "Executing autosetup..."
/run_autosetup.sh
echo "Done autosetup"

/run_soffice.sh &

echo "Starting up odoo"
if [[ "$IS_ODOO_CRONJOB" == "1" ]]; then
    echo 'Starting odoo cronjobs'
    CONFIG=config_cronjob
    EXEC="$ODOO_EXECUTABLE_CRONJOBS"
else
    echo 'Starting odoo web'
    CONFIG=config_webserver
    EXEC="$ODOO_EXECUTABLE_GEVENT"
fi
sudo -E -H -u "$ODOO_USER" $SERVER_DIR/$EXEC -c "$CONFIG_DIR/$CONFIG"  -d "$DBNAME" --log-level="$ODOO_LOG_LEVEL"
