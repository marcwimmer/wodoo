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

    def __getattribute__(self, name):
        if name == '_logger':
            return logging.getLogger('model.{}'.format(self._name))
        return super(Base, self).__getattribute__(name)

    def add_todo_fields(self, *fields_array):
        # shortcut for odoo syntax
        assert all(isinstance(x, str) for x in fields_array)
        for field in fields_array:
            obj_field = self._fields[field]
            if not obj_field.store:
                self._logger.warning("Field {} is not stored. Not recomputed now.".format(field))
            self.env.add_todo(obj_field, self)

    def remove_field_cache(self, *fields_array):
        for f in fields_array:
            self.env.cache.invalidate(spec=[(self._fields[f], self.ids)])

    def recompute_fields(self, *fields_array):
        """
        Bug: if called from migration script in modules, then
             cached value exists and no recomputation is done (store=True, and tested for float field)
             Trying to release cache here - may impact other workflows.
             Trying to release cache values for just the field.

        """
        self.remove_field_cache(*fields_array)
        model = self.env[self._name]
        self.add_todo_fields(*fields_array)
        model.recompute()

    tools = Tools()
