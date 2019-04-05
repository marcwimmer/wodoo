#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [ -z "$1" ]; then
    echo "Usage: import_i18n de_DE pofilepath"
    exit -1
fi

LANG="$1"
FILEPATH="$2"
if [ -z "$FILEPATH" ]; then
    echo "Language Code and/or Path missing!"
	echo
	echo "Please provide the path relative to customs e.g. modules/mod1/i18n/de.po"
    exit -1
fi

echo "Importing lang file $FILEPATH"
sudo -E -H -u "$ODOO_USER" \
	"$SERVER_DIR/$ODOO_EXECUTABLE" \
	-c "$CONFIG_DIR/config_i18n" \
	--log-level=warn \
	--stop-after-init \
	-d "$DBNAME" \
	-l "$LANG" \
	--i18n-import="$FILEPATH" \
	--i18n-overwrite
