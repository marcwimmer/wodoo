from odoo import models, api, fields, _
from mako.template import Template

class Formatter(models.Model):
    _name = 'data.police.formatter'
    model = fields.Char("Model", size=128)
    format = fields.Char('Format')

    @api.model
    def do_format(self, instance):
        formatter = self.search([('model', '=', instance._name)])

        if not formatter:
            return instance.name_get()[0][1]
        formatter = formatter[0]

        t = Template(formatter['format'])
        res = t.render(obj=instance)
        return res
