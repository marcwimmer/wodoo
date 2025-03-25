from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    dummy1 = fields.Char("Dummy1")
