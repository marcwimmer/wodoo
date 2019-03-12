#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [ -z "$1" ]; then
    echo "Usage: import_i18n de_DE [filepath of po file optional]"
    exit -1
fi

LANG="$1"
MODULES="$2"

export_dir="${ADDONS_CUSTOMS}/$MODULES"
if [[ -z "$(find "$export_dir" 2>/dev/null)" ]]; then
	echo "Symlink not found: $export_dir"
fi

if [[ ! -d "$export_dir/i18n" ]]; then
	mkdir -p "$export_dir/i18n"
fi

TMP="$(mktemp -u)"
mkdir -p "$TMP"
chown -R "$ODOO_USER" "$TMP"
TMP=${TMP}/$LANG.po
sudo -E -H -u "$ODOO_USER" \
	"$SERVER_DIR/$ODOO_EXECUTABLE" \
	-c "$CONFIG_DIR/config_openerp" \
	--log-level=warn \
	--stop-after-init \
	-d "$DBNAME" \
	-l "$LANG" \
	--i18n-export="$TMP" \
	--modules="$MODULES"

DEST_PATH="$export_dir/i18n/$LANG.po" 
cp "$TMP" "$DEST_PATH"
chown -R "$ODOO_USER" $(dirname "$DEST_PATH")
if [[ "$OWNER_GID" != "" ]]; then
    chgrp -R "$OWNER_GID" $(dirname "$DEST_PATH")
fi
