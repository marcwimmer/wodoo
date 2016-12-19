#!/bin/bash
set -e
set -x

locale-gen en_US.UTF-8
update-locale

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8

source /env.sh
source /opt/openerp/admin/setup_bash

if [[ -z "$CUSTOMS" ]]; then
    echo "CUSTOMS required!"
    exit -1
fi

# Setting up productive odoo
echo Starting odoo for customs $CUSTOMS

/set_permissions.sh
ODOO_VERSION=$(cat /opt/openerp/customs/$CUSTOMS/.version)
echo "Odoo version is $ODOO_VERSION"

# use virtualenv installed packages for odoo

echo "Executing autosetup..."
/run_autosetup.sh $ODOO_PROD
echo "Done autosetup"

echo on version 6.1 start soffice
if [[ "$ODOO_VERSION" == "6.1" ]]; then
    sudo -H -u odoo /usr/bin/soffice --nologo --nofirststartwizard --headless --norestore --invisible --accept="socket,host=localhostort=8100,tcpNoDelay=1;urp;" &

fi

echo "Starting up odoo"
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=debug &
sudo -E -H -u odoo /opt/openerp/versions/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=debug &
sleep 3

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

    pgrep -f openerp > /dev/null || {
        [[ -f /tmp/debugging ]] || {
            echo 'exiting - no odoo here...'
            exit -1
        }
    }

    sleep 1

done
