from odoo import models, api, _

class Product(models.Model):
    _inherit = 'product.product'

    @api.one
    def check_buy_articles_that_have_no_price(self):
        SI = self.env["product.supplierinfo"]
        has_price = bool(self.standard_price)
        if has_price:
            return True

        si = SI.search([('product_id', '=', self.id)])
        prices = si.mapped('price')
        has_price = any(prices)
        if not has_price:
            line_ids = self.env["account.invoice.line"].search([('invoice_id.type', '=', 'in_invoice'), ('product_id', '=', self.id)])
            if line_ids:
                has_price = True

        return has_price
