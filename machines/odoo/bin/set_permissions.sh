#!/bin/bash
echo "setting ownership of /opt/oefiles to odoo"
chown odoo:odoo /opt/oefiles -R
chown odoo:odoo /opt/openerp/ -R
chown odoo:odoo /opt/toprint -R
