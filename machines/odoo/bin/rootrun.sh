#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

/run.sh
