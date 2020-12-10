from odoo import models, api, _

class Product(models.Model):
    _inherit = 'product.product'

    @api.one
    def check_incoming_noproduction_nopicking(self):
        product = self
        if product.type not in ['product']:
            return True

        moves = self.env['stock.move'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', 'not in', ('transit',  'internal')),
            ('state', 'not in', ['done', 'cancel', 'draft']),
            ('location_dest_id.usage', 'in', ('internal', 'transit'))
        ])
        for move in moves:
            if move.picking_id or move.picking_id.state in ['cancel']:
                continue
            if move.production_id or move.production_id.state in ['cancel']:
                continue
            if move.purchase_line_id and move.purchase_line_id.order_id.state not in ['done', 'cancel']:
                continue

            raise Exception("stock.move#id:{} - Date: {} - Quantity: {}".format(
                move.id,
                move.create_date,
                move.product_qty,
            ))
        return True
