from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError
class Container(models.Model):
    _name = 'docker.container'

    name = fields.Char("Name")

    @api.one
    def restart(self):
        from pudb import set_trace
        set_trace()
