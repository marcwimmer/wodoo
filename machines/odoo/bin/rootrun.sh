#!/bin/bash
set -e
set +x
[[ "$VERBOSE" == "1" ]] && set -x

echo "IS_ODOO_CRONJOB: $IS_ODOO_CRONJOB"
echo "RUN_ODOO_CRONJOBS: $RUN_ODOO_CRONJOBS"

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_ODOO_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi
if [[ "$IS_ODOO_QUEUEJOB" == "1" && "$RUN_ODOO_QUEUEJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

/run.sh
