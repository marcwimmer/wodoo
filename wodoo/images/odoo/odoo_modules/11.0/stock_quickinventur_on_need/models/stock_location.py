from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Location(models.Model):
    _inherit = 'stock.location'

    auto_inventory_on_missing_stock = fields.Boolean("Auto Inventory on missing stock")
