from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    dummy2 = fields.Char("Dummy2")
