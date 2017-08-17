#!/usr/bin/python

"""

Input: odoo configuration file:

{
    'ip_pool': {
        'start': '10.28.0.10',
        'end': '10.28.5.200',
        'netmask': '255.255.0.0',
    },

    'internal_hosts': [
        {
            'odoo': {},
            'asterisk': {
                'fixed_ip': '.....',  # optional
            }
        }
    ],


}


"""
