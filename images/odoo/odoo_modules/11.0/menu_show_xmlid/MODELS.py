from odoo import models, fields, api


@api.multi
def get_xmlid(self):
    ids = [x.id for x in self]
    self.env.cr.execute("select res_id, module, name from ir_model_data where res_id in (%s) and model='%s'" % (','.join([str(x) for x in ids] + ["-1"]), self._name))
    records = self.env.cr.fetchall()

    for obj in self:
        r = [x for x in records if x[0] == obj.id]
        if r:
            r = r[0]
            obj.xml_id = "%s.%s" % (r[1], r[2])
        else:
            # Odoo Studio Customization needs that; if xml_id startswith studio customization
            obj.xml_id = ""

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
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_actions_act_window(models.Model):
    _inherit = 'ir.actions.act_window'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_actions_report(models.Model):
    _inherit = 'ir.actions.report'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_rule(models.Model):
    _inherit = 'ir.rule'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class res_groups(models.Model):
    _inherit = 'res.groups'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class ir_model_access(models.Model):
    _inherit = 'ir.model.access'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)

class sequence(models.Model):
    _inherit = 'ir.sequence'
    xml_id = fields.Char(compute=get_xmlid, string="Xml Id", search=_search_xml_id)
