from datetime import datetime
import logging
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression

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
                return expression.OR([
                    expression.AND([[(f1, '=', False)], [(f2, '=', False)]]),
                    expression.AND([[(f1, '<=', d)], [(f2, '>=', d)]]),
                    expression.AND([[(f1, '<=', d)], [(f2, '=', False)]]),
                    expression.AND([[(f1, '=', False)], [(f2, '>=', False)]]),
                ])
            else:
                return expression.OR([
                    [(f1, '>', d)],
                    [(f2, '<', d)],
                ])
        raise Exception("not impl")

class ComputeModel(models.AbstractModel):
    _name = 'model.mixin'
    model = fields.Char(string='Model')
    model_id = fields.Many2one('ir.model', compute='compute_model', string='Model')

    @api.depends('model')
    def compute_model(self):
        for self in self:
            if self.model:
                model_id = self.env['ir.model'].search([('model', '=', self.model)], limit=1)
                self.model_id = model_id

    @api.model
    def default_get(self, fields):
        res = super(ComputeModel, self).default_get(fields)
        res['model'] = self._name
        return res
