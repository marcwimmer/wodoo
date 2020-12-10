from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Lang(models.Model):
    _inherit = 'res.lang'

    excel_format_date = fields.Char("Excel Format Date")
    excel_format_num = fields.Char("Excel Format Integer")
    excel_format_money = fields.Char("Excel Format Money")

    @api.model
    def _update_excel_formattings_defaults(self):
        lang = self.env.ref('base.lang_en')
        if not lang.excel_format_num:
            lang.excel_format_num = "#.00"
        if not lang.excel_format_money:
            lang.excel_format_money = "#,##0.00;[RED]-#,##0.00"
        if not lang.excel_format_date:
            lang.excel_format_date = "mm/dd/yyyy"
