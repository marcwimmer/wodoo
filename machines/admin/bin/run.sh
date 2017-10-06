#!/bin/bash

dev=""

if [[ "$ADMINDEBUG" == "1" ]]; then
	dev="--dev=all, pudb, reload, qweb, werkzeug, xmlall"
fi

if [[ "$1" == "dropdb" ]]; then
	gosu postgres psql template1 <<- EOF
	drop database admin;
	EOF
fi

gosu odoo "/opt/src/odoo/odoo-bin" \
	-c "/opt/config_openerp"  \
	-d "$DBNAME" \
	--log-level="$LOGLEVEL" \
	"$dev"
