import os

def get_env():
    V = float(os.getenv("ODOO_VERSION"))
    if V <= 8.0:
        return {
            "ODOO_PYTHON_VERSION": "2",
            "ODOO_EXECUTABLE_GEVENT": "openerp-server",
            "ODOO_EXECUTABLE_CRONJOBS": "openerp-server",
            "ODOO_EXECUTABLE_DEBUG": "openerp-server",
            "ODOO_EXECUTABLE": 'openerp-server',
        }
    elif V == 9.0:
        return {
            "ODOO_PYTHON_VERSION": "2",
            "ODOO_EXECUTABLE_GEVENT": "openerp-gevent",
            "ODOO_EXECUTABLE_CRONJOBS": "openerp-server",
            "ODOO_EXECUTABLE_DEBUG": "openerp-server",
            "ODOO_EXECUTABLE": 'openerp-server',
        }
    elif V == 10.0:
        return {
            "ODOO_PYTHON_VERSION": "2",
            "ODOO_EXECUTABLE_GEVENT": "openerp-gevent",
            "ODOO_EXECUTABLE_CRONJOBS": "openerp-server",
            "ODOO_EXECUTABLE_DEBUG": "openerp-server",
            "ODOO_EXECUTABLE": 'openerp-server',
        }
    elif V >= 11.0:
        return {
            "ODOO_PYTHON_VERSION": "3",
            "ODOO_EXECUTABLE_GEVENT": "odoo-bin gevent",
            "ODOO_EXECUTABLE_CRONJOBS": "odoo-bin",
            "ODOO_EXECUTABLE_DEBUG": "odoo-bin",
            "ODOO_EXECUTABLE": 'odoo-bin',
        }
    raise Exception("Unhandled: {}".format(V))
