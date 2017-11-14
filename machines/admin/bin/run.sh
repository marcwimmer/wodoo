#!/bin/bash

if [[ "$ADMINDEBUG" == "1" ]]; then
	dev="--dev='all, pudb, reload, qweb, werkzeug, xmlall'"
fi

if [[ "$1" == "dropdb" ]]; then
	gosu postgres psql template1 <<- EOF
	drop database admin;
	EOF
fi

declare -a cmd
cmd+=(gosu odoo)
cmd+=("/opt/src/odoo/odoo-bin")
cmd+=("-c" "/opt/config_openerp")
cmd+=("-d" "$DBNAME")
cmd+=("--log-level"  "$LOGLEVEL")
if [[ -n "$dev" ]]; then
	cmd+=("$dev")
fi

cmdupdate=("${cmd[@]}")
cmdupdate+=("-u container_admin")
cmdupdate+=("--stop-after-init")
eval "${cmdupdate[@]}"

eval "${cmd[@]}"
