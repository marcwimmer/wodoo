#!/bin/bash

rsync /opt/src/admin/ /opt/openerp/admin -arP --delete --exclude=.git
rsync /opt/src/customs/$CUSTOMS/ /opt/openerp/active_customs -arP --delete --exclude=.git
/opt/openerp/admin/oeln $CUSTOMS
sudo -E -H -u odoo /opt/openerp/versions/server/odoo.py shell -d $DBNAME -c /home/odoo/config_debug
