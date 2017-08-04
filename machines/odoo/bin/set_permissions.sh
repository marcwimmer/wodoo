#!/bin/bash
set -x
echo "setting ownership of /opt/oefiles to odoo"
chown odoo:odoo /opt/oefiles -R
echo "setting ownership of /opt/openerp to odoo"
chown odoo:odoo /opt/openerp/ -R
echo "setting ownership of $CUPS_TOPRINT to odoo"
chown odoo:odoo $CUPS_TOPRINT -R

