#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set +x

export IS_ODOO_CRONJOB=1
/run.sh
