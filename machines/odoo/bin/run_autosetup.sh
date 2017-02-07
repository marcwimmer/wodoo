#!/bin/bash
# Autosetup searches in /opt/openerp/customs/$CUSTOMS/autosetup for 
# *.sh files; makes them executable and executes them
# You can do setup there, like deploying ssh keys and so on
set -e

ODOO_PROD="$1"

if [[ "$RUN_AUTOSETUP" == "1" ]]; then
    cd /opt/openerp/active_customs
    if [[ ! -d autosetup ]]; then
        exit 0
    fi
    cd autosetup

    for file in *.sh; do
        echo "executing $file"
        eval "bash ./$file $ODOO_PROD"
    done
fi
