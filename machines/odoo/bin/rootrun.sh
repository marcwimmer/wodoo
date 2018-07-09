#!/bin/bash
set -e
set -x
[[ "$VERBOSE" == "1" ]] && set -x

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_ODOO_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

if [[ "$RUN_RSYNCED" == "1" ]]; then
    rsync --daemon
fi

/run.sh
