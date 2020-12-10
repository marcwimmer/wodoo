from odoo import models, api, _

class DP(models.Model):
    _inherit = 'res.partner'

    @api.one
    def fix_check_customer_company(self):
        if self.customer and not self.is_company:
            self.is_company = True
