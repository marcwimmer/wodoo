from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError
class NewBranch(models.TransientModel):
    _name = 'branch.new'

    name = fields.Char("Name")

    @api.multi
    def ok(self):
        from pudb import set_trace
        set_trace()
