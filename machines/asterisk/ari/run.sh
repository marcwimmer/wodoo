#!/bin/bash
set -e
set -x

if [[ "$RUN_ASTERISK" == "0" ]]; then
    echo "asterisk is turned off by customs.env - good bye! :)"
    exit 0
fi

cd /opt/src

# always updating
rm /opt/src/* -Rf || true
git clone --branch deploy git.mt-software.de:/git/openerp/modules/asterisk_ari
echo 'done updating ari'

if [[ -n "$DO_INIT" || -n "$DO_UPDATE" ]]; then
    exit 0
fi

echo "Waiting for asterisk to arrive at port $PORT_ASTERISK"
while true; do
    if $(nc -z $HOST_ASTERISK $PORT_ASTERISK); then
        break
    fi
    sleep 1
done
echo "Asterisk arrived! connecting..."

echo "Waiting for odoo to arrive at port $ODOO_PORT"
while true; do
    if $(nc -z $ODOO_HOST $ODOO_PORT); then
        break
    fi
    sleep 1
done
echo "Odoo arrived! connecting..."

pgre -f nginx || /usr/sbin/nginx

/runprod.sh &

set +x
while true;
do
    pgrep -f ariconnector.py > /dev/null || {
        [[ ! -f /tmp/debugging ]] && {
            echo 'Ari seems dead and no debugging'
            exit -1
        }
    }
    sleep 1
done
