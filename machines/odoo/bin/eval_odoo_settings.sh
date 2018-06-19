#!/bin/bash

case "$ODOO_VERSION" in
    "6.0"|"6.1"|"7.0"|"8.0")
        export ODOO_PYTHON_VERSION="2"
        export ODOO_EXECUTABLE_GEVENT="openerp-server"
        export ODOO_EXECUTABLE_CRONJOBS="openerp-server"
        ;;
        
    "9.0")
        export ODOO_PYTHON_VERSION="2"
        export ODOO_EXECUTABLE_GEVENT="openerp-gevent"
        export ODOO_EXECUTABLE_CRONJOBS="openerp-server"
        ;;

    "11.0")
        export ODOO_PYTHON_VERSION="3"
        export ODOO_EXECUTABLE_GEVENT="odoo-bin"
        export ODOO_EXECUTABLE_CRONJOBS="odoo-bin"
        ;;

esac
