import time
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class ExcelDemo(models.AbstractModel):
    _name = 'report.xls_partners'

    def excel(self, objects):
        result = {}

        #result['records'] = self.env['res.partner'].search([])
        #result['columns'] = ['name']

        # or
        result['records'] = self.env['res.partner'].search([]).read(['name', 'street'])
        result['model'] = 'res.partner'
        for i, x in enumerate(result['records']):
            x['__color_name'] = {
                0: 'red',
                1: 'orange',
                2: 'blue',
            }[i % 3]

        return {
            "Partners (this is sheet1)": result,
        }
