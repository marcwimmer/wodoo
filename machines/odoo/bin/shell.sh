#!/bin/bash
sudo -E -H -u odoo /opt/openerp/versions/server/odoo.py shell -d $DBNAME -c /home/odoo/config_debug
