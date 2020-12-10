from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
# class Base(models.AbstractModel):
    # _inherit = 'base'

    # @api.model
    # def create(self, vals):
        # from pudb import set_trace
        # set_trace()
        # result = super().create(vals)
        # if 'fuzzy.mixin' in getattr(self, '_inherits', []):
            # result._update_fuzzy_words()
        # return result

    # def write(self, vals):
        # from pudb import set_trace
        # set_trace()
        # result = super().write(vals)
        # if any(x in vals for x in self._get_fuzzy_fields()):
            # self._update_fuzzy_words()
        # return result

    # def unlink(self):
        # from pudb import set_trace
        # set_trace()
        # self.env['fuzzy.words'].sudo().search([
            # ('res_model', '=', self._name),
            # ('res_id', 'in', self.ids)
        # ]).unlink()
        # result = super().unlink()
        # return result
