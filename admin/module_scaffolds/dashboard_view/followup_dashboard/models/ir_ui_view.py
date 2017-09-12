from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError

class View(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('followup_dashboard', 'Followup Dashboard')])
