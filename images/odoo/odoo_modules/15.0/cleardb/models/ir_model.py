from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Model(models.Model):
    _inherit = 'ir.model'

    clear_db = fields.Boolean("Clear DB")

    def _reflect_model_params(self, model):
        res = super(Model, self)._reflect_model_params(model)
        res['clear_db'] = getattr(model, '_clear_db', False)
        return res
