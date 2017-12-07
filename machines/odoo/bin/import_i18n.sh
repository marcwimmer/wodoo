#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [ -z "$1" ]; then
    echo "Usage: import_i18n de_DE [filepath of po file optional]"
    exit -1
fi
/apply-env-to-config.sh

LANG=$1
if [ -z "$LANG" ]; then
    echo "Language Code Missing!"
    exit -1
fi

path=${ADDONS_CUSTOMS}/${2}/i18n/$LANG.po

if [[ -f "$path" ]]; then

	sudo -E -H -u "$ODOO_USER" \
		"$SERVER_DIR/openerp-server" \
		-c "$CONFIG_DIR/config_openerp" \
		--log-level=warn \
		--stop-after-init \
		-d "$DBNAME" \
		-l "$LANG" \
		--i18n-import="$path" \
		--i18n-overwrite
fi
