from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    @api.model
    def set_updatable(self, xmlid):
        module, name = xmlid.split('.')
        self.search([('module', '=', module), ('name', '=', name)]).write({
            'noupdate': False,
        })
