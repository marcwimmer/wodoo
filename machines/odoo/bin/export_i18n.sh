#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [ -z "$1" ]; then
    echo "Usage: import_i18n de_DE [filepath of po file optional]"
    exit -1
fi

LANG=$1
MODULES=$2

/apply-env-to-config.sh

sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp --log-level=warn --stop-after-init -d $DBNAME -l $LANG --i18n-export=/tmp/export.po --modules=$MODULES

cp /tmp/export.po $LANG_EXPORT_DIR/export.po
