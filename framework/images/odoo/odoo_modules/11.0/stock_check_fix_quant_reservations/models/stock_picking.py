from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Picking(models.Model):
    _inherit = 'stock.picking'

    def fix_reservations(self):
        for product in self.move_line_ids.mapped('product_id'):
            self.env['stock.quant'].search([
                ('location_id.usage', '=', 'internal'),
                ('product_id', '=', product.id),
            ])
