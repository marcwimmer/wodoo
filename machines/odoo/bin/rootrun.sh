#!/bin/bash
set -e

#chmod a+w -R $LIBREOFFICE_SEND
#chmod a+w -R $LIBREOFFICE_RECEIVE

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

/run.sh
