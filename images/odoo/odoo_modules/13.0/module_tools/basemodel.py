import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from .dttools import *
from .dttools import str2date
from .dttools import date_type
from .stringtools import *
from .logtools import *
from .dbtools import *
from .pdftools import *
from .other import *
from .action_window_tools import *

class Tools(object):

    def __getattribute__(self, name):
        try:
            return globals()[name]
        except Exception:
            return super().__getattribute__(name)

    def user_date(self, env, date):
        if not date:
            return False
        date = str2date(date)
        lang = env['res.lang'].sudo().search([('code', '=', env.user.lang)])
        if not lang:
            return date
        if not date:
            return date

        converted_date = str2date(date)
        if date_type(date) == 'date':
            return converted_date.strftime(lang.date_format)
        if date_type(date) == 'datetime':
            return converted_date.strftime(lang.date_format + " " + lang.time_format)
        raise UserError("Error converting {}".format(date))

class Base(models.AbstractModel):

    _inherit = 'base'
    _logger = logging.getLogger('odoo_default_logger')
    tools = Tools()
