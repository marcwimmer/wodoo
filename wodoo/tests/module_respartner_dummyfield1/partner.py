from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Partner(models.Model):
    _inherit = 'res.partner'

    dummy1 = fields.Char("Dummy1")
