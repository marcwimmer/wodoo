from odoo import api
from odoo.api import attrsetter

def check_args(args):
    for x in args:
        if not isinstance(x, str):
            raise Exception("String required, not so: {}".format(x))
        if '.' in x:
            raise Exception("Relations not supported at the moment: {}".format(x))

def recordchange(*args):
    check_args(args)
    return attrsetter('_recordchange', args)

def fieldchange(*args):
    check_args(args)
    return attrsetter('_fieldchange', args)

def monkeypatch():
    api.recordchange = recordchange
    api.fieldchange = fieldchange
