#!/bin/bash
gosu odoo "/opt/src/odoo/odoo-bin" \
	-c "/opt/config_openerp"  \
	-d "$DBNAME" \
	--log-level="$LOGLEVEL"
