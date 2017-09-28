#!/bin/bash

dev=""

if [[ "$ADMINDEBUG" == "1" ]]; then
	dev="--dev=all"
fi

gosu odoo "/opt/src/odoo/odoo-bin" \
	-c "/opt/config_openerp"  \
	-d "$DBNAME" \
	--log-level="$LOGLEVEL" \
	"$dev"
