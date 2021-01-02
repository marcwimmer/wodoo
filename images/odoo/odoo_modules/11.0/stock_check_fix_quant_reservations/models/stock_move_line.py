from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.model
    def create(self, vals):
        self = super().create(vals)
        products = self.mapped('product_id')
        if 'internal' in self.mapped('location_id.usage'):
            self.env['stock.quant']._check_stock_quants(products)
        return self

    def write(self, vals):
        products = self.mapped('product_id')
        result = super().write(vals)
        if 'internal' in self.mapped('location_id.usage'):
            self.env['stock.quant']._check_stock_quants(products)
        return result

    def unlink(self):
        products = self.env['product.product']
        if 'internal' in self.mapped('location_id.usage'):
            products = self.mapped('product_id')
        result = super().unlink()
        self.env['stock.quant']._check_stock_quants(products)
        return result
