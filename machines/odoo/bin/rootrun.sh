#!/bin/bash

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi


locale-gen en_US.UTF-8
update-locale

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8

if [[ "$IS_ODOO_CRONJOB" == "1" && "$RUN_CRONJOBS" != "1" ]]; then
    echo "Cronjobs shall not run. Good-bye!"
    exit 0
fi

/run.sh
