from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Report(models.Model):
    _inherit = 'ir.actions.report'

    test_url = fields.Char(compute="_get_test_url")

    def _get_test_url(self):
        for self in self:
            try:
                id = self.env[self.model].search([], limit=1, order='id desc').id
            except Exception:
                id = 0
            self.test_url = '/report/html/{}/{}'.format(self.report_name, id)
