#!/bin/bash
set -e
set -x

/sync_source.sh

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LANGUAGE=en_US.UTF-8 

echo on version 6.1 start soffice
if [[ "$ODOO_VERSION" == "6.1" ]]; then
    sudo -H -u odoo /usr/bin/soffice --nologo --nofirststartwizard --headless --norestore --invisible --accept="socket,host=localhostort=8100,tcpNoDelay=1;urp;" &

fi

echo "Starting up odoo"
if [[ "$IS_ODOO_CRONJOB" == "1" ]]; then
    echo 'Starting odoo cronjobs'
    sudo -E -H -u odoo /opt/openerp/versions/server/openerp-server -c /home/odoo/config_openerp -d $DBNAME --log-level=$LOGLEVEL
else
    echo 'Starting odoo gevent'
    sudo -E -H -u odoo /opt/openerp/versions/server/openerp-gevent -c /home/odoo/config_gevent  -d $DBNAME --log-level=$LOGLEVEL
fi
