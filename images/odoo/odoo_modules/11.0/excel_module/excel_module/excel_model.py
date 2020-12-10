import base64
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class Excel(models.AbstractModel):
    _name = 'excel.workbook'

    @api.model
    def new_workbook(self, constant_memory=False):
        """
        wb, output = self.new_workbook()
        ws = wb.add_worksheet(title)

        when finished:
        wb.close()
        output.seek(0)
        data = output.read()
        """
        return self.env['excel.maker'].get_workbook(constant_memory=constant_memory)

    @api.model
    def finish_workbook(self, wb, output):
        wb.close()
        output.seek(0)
        content = output.read()
        content = self.env['excel.maker'].auto_fit_columns(content)
        return base64.encodestring(content)
