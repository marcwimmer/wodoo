from odoo import api, fields, models
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class Recompute(models.AbstractModel):
    _name = 'recompute.parent.store'

    def cron_recompute_parent_store(self):
        for model in self.env['ir.model'].search([]):
            try:
                obj = self.env[model.model]
            except KeyError:
                pass
            else:
                obj._parent_store_compute()
