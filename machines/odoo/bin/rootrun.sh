#!/bin/bash
set -e

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

/run.sh
