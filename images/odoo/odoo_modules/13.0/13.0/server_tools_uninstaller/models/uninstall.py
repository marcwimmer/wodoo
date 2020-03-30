from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class Uninstaller(models.AbstractModel):
    _name = 'server.tools.uninstaller'

    @api.model
    def uninstall(self):
        raise Exception('implement me!')
