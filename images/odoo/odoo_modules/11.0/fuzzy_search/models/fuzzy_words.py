from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class FuzzyWords(models.Model):
    _name = 'fuzzy.words'

    res_model = fields.Char("", required=True, index=True)
    res_id = fields.Integer("", required=True, index=True)
    word = fields.Char("", translate=False, index=True)
