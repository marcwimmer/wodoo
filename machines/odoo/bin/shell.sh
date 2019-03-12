#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

source /eval_odoo_settings.sh
/apply-env-to-config.py

OPTIONS=""
case "$ODOO_VERSION" in
    "7.0"|"8.0"|"9.0"|"10.0")
        OPTIONS=""
        ;;
    "11.0")
        OPTIONS="--shell-interface=ipython"
        ;;
esac
sudo -E -H -u $ODOO_USER $SERVER_DIR/$ODOO_EXECUTABLE_CRONJOBS shell -d $DBNAME -c $CONFIG_DIR/config_shell $OPTIONS
