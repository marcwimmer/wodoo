from odoo import models, api, _

class Product(models.Model):
    _inherit = 'product.product'

    @api.one
    def check_product_account(self):
        for company in self.env['res.company'].search([]):
            if not self.with_context(force_company=company.id).property_account_income_id:
                raise Exception("Property Account Incoming missing for {} {} {}".format(company.name, self.default_code or '', self.name or ''))


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    def check_invoice_partners(self):
        if not self.move_id:
            return True

        partners = self.mapped('move_id.line_ids.partner_id')

        if len(partners) == 1:
            if partners[0] != self.partner_id.commercial_partner_id:
                return "Invoice partner mismatch: {} {}[ partner-id: {} ] vs. {}[ partner-id: {} ]".format(
                    self.number,
                    self.partner_id.commercial_partner_id.name,
                    self.partner_id.commercial_partner_id.id,
                    partners[0].name,
                    partners[0].id
                )
        return True


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.one
    def check_missing_payment_terms_and_personal_accounts(self):
        param_fields = []

        if self.customer:
            param_fields += ['property_payment_term_id', 'property_account_receivable_id']
        elif self.supplier:
            param_fields += ['property_supplier_payment_term_id', 'property_account_payable_id']
        for f in param_fields:
            self.env.cr.execute("select count(*) from ir_property where name =%s and res_id='res.partner,{}'".format(self.id), [f])
            if not self.env.cr.fetchone()[0]:
                return False
        return True
