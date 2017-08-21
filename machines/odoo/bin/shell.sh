#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x

/sync_source.sh
/apply-env-to-config.sh
sudo -E -H -u odoo /opt/odoo/server/odoo.py shell -d $DBNAME -c /home/odoo/config_shell
