#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

/apply-env-to-config.sh
sudo -E -H -u $ODOO_USER $SERVER_DIR/$ODOO_EXECUTABLE shell -d $DBNAME -c $CONFIG_DIR/config_shell
