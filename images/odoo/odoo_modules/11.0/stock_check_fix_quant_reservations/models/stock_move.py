from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class StockMove(models.Model):
    _inherit = 'stock.move'

    # def _action_done(self):
        # result = super()._action_done()
        # # fix quants
        # quants = self.env['stock.quant'].search([('product_id', 'in', self.mapped('product_id').ids)])
        # quants.fix_reservation()

        # return result
