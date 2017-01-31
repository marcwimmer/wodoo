#!/bin/bash
/run.sh &

sleep 20

set +x
while true;
do
    if [[ -f /tmp/stop ]]; then
        pkill -9 -f openerp-server || true
        rm /tmp/stop
    fi

    if [[ -f /tmp/start ]]; then
        rm /tmp/start
        eval $START_LINE &
    fi

    if [[ -f /tmp/restart ]]; then
        rm /tmp/restart
        /opt/openerp/admin/oekill
        /run.sh
    fi

    pgrep -f openerp > /dev/null || {
        [[ -f /tmp/debugging ]] || {
            echo 'exiting - no odoo here...'
            exit -1
        }
    }

    sleep 1

done
