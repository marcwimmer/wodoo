from lxml import etree
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            doc = etree.XML(result['arch'])
            for name, field in filter(lambda x: x[1].type in ['float', 'monetary'], list(self._fields.items())):
                node = doc.xpath("//field[@name='{}']".format(name))
                if not node:
                    continue
                node = node[0]
                if node.get('group'):
                    continue
                node.attrib['sum'] = field.string
            result['arch'], new_fields = self.env['ir.ui.view'].postprocess_and_fields(self._name, doc, view_id)
        return result
