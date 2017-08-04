#!/bin/bash

if [[ "$RUN_RADICALE" != "1" ]]; then
    echo 'Radicale is turned off by customs.env'
    exit 0
fi


#copy config template to destination and adjust settings
cp /etc/radicale/config.template /etc/radicale/config
sed -i "s/__DB__/$DBNAME/g" /etc/radicale/config
sed -i "s/__USER__/$RADICALE_USER/g" /etc/radicale/config
sed -i "s/__PASSWORD__/$RADICALE_PASSWORD/g" /etc/radicale/config

cd /opt
LN_PYTHONLIBS=/usr/local/lib/python2.7/dist-packages/radicale_odoo
rm radicale || true
rm $LN_PYTHONLIBS || true
ln -s /opt/openerp/active_customs/common/calendar_ics/RadicalePatched-1.1.1 radicale
ln -s /opt/openerp/active_customs/common/calendar_ics/rc $LN_PYTHONLIBS 

cd /opt/radicale
export PYTHONPATH=. 
python radicale.py -C /etc/radicale/config
