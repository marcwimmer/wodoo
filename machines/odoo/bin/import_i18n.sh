#!/bin/bash
set -ex
if [ -z "$1" ]; then
    echo "Usage: import_i18n de_DE [filepath of po file optional]"
    exit -1
fi
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

LANG=$1
FILE=$2
if [ -z "$LANG" ]; then
    echo "Language Code Missing!"
    exit -1
fi
/apply-env-to-config.sh
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp --log-level=warn --stop-after-init -d $DBNAME -l $LANG --i18n-import=$FILE --i18n-overwrite
