from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class RestoreWebIcons(models.AbstractModel):
    _name = 'web.restore.icons'

    @api.model
    def restore(self):
        for x in self.env['ir.ui.menu'].search([]):
            if x.web_icon:
                x.web_icon_data = x._compute_web_icon_data(x.web_icon)
