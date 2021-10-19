from odoo import models, fields, api


def _get_xmlid(self):
    ids = self.get_external_id()
    for obj in self:
        obj.xml_id = ids[obj.id]

def _search_xml_id(self, operator, value):
    crits = [('model', '=', self._name)]

    if value and "." in value:
        module, name = value.split('.')
        crits = [('name', operator, name), ('module', operator, module)]
    else:
        name = value
        crits = [('name', operator, value)]

    ids = self.env['ir.model.data'].sudo().search(crits).mapped('res_id')
    return [('id', 'in', ids)]

class ir_ui_menu(models.Model):
    _inherit = 'ir.ui.menu'
    xml_id = fields.Char(compute=_get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_rule(models.Model):
    _inherit = 'ir.rule'
    xml_id = fields.Char(compute=_get_xmlid, string="Xml Id", search=_search_xml_id)

class res_groups(models.Model):
    _inherit = 'res.groups'
    xml_id = fields.Char(compute=_get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_model_access(models.Model):
    _inherit = 'ir.model.access'
    xml_id = fields.Char(compute=_get_xmlid, string="Xml Id", search=_search_xml_id)
