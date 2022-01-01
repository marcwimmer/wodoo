from odoo import api, fields, models
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class Report(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection(selection_add=[('excel', 'Excel')])
