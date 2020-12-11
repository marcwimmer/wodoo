from datetime import datetime
import logging
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class MixinValidNow(models.AbstractModel):
    _name = 'mixin.valid_now'

    """

    class A(models.Model):
        valid_now = fields.Boolean(computed='_get_validnow', string="Valid Now", search="_search_valid_now", store=False)

        @api.one
        def _get_validnow(self):
            self.valid_now = self.mixin_valid_now_get(self.date_start, self.date_stop)

        def _search_valid_now(self, operator, value):
            return self.mixin_valid_now_search(operator, value, 'date_start', 'date_stop')


    """

    def mixin_valid_now_get(self, d1, d2):
        now = datetime.utcnow().date()
        if self.date_start or self.date_stop:
            return self.tools.date_in_range(now, self.date_start, self.date_stop)
        else:
            return True

    def mixin_valid_now_search(self, operator, value, f1, f2):
        supported = ['=', '!=']
        assert operator in supported, 'only {} supported'.format(supported)
        if operator == "!=":
            operator = '='
            value = not value

        d = datetime.utcnow().strftime("%Y-%m-%d")

        if operator == '=':
            if value:
                return [
                    '|', '|', '|', '&', (f1, '=', False), (f2, '=', False),
                    '&', (f1, '<=', d), (f2, '>=', d),
                    '&', (f1, '<=', d), (f2, '=', False),
                    '&', (f1, '=', False), (f2, '>=', d),
                ]
            else:
                return [
                    '|',
                    (f1, '>', d)
                    (f2, '<', d)
                ]
        raise Exception("not impl")
