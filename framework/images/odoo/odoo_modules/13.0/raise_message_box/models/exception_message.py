import odoo
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError, Warning

class MessageBox(Warning):
    pass


odoo.exceptions.MessageBox = MessageBox
