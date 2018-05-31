#!/bin/bash
set -e
set -x
[[ "$VERBOSE" == "1" ]] && set -x

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

# link the docker mounted source; debug.sh
# will symlink the rsynced version later
ln -s /opt/odoo/active_customs_mounted /opt/odoo/active_customs

rsync --daemon

/run.sh
