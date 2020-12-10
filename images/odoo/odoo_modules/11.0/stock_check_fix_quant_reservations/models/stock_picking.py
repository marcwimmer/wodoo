from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Picking(models.Model):
    _inherit = 'stock.picking'

    def fix_reservations(self):
        for move_line in self.move_line_ids.filtered(lambda x: x.product_id.type == 'product' and x.state not in ['done', 'cancel']):
            if not move_line.product_uom_qty:
                continue
            self.env['stock.quant']._get_status(
                fix=True,
                product=move_line.product_id,
                expects_stock_at_location=move_line.location_id.id,
            )
