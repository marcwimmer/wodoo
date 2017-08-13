#!/bin/bash
# Autosetup searches in /opt/odoo/customs/$CUSTOMS/autosetup for 
# *.sh files; makes them executable and executes them
# You can do setup there, like deploying ssh keys and so on
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ "$RUN_AUTOSETUP" == "1" ]]; then
    cd /opt/odoo/active_customs
    if [[ ! -d autosetup ]]; then
        exit 0
    fi
    cd autosetup

    for file in *.sh; do
        echo "executing $file"
        eval "bash ./$file $ODOO_AUTOSETUP_PARAM"
    done
fi
