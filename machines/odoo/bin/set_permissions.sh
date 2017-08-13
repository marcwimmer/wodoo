#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
echo "setting ownership of /opt/files to odoo"
chown odoo:odoo /opt/files -R
echo "setting ownership of /opt/odoo to odoo"
chown odoo:odoo /opt/odoo/ -R

