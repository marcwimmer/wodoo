from lxml import etree
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError

class Base(models.AbstractModel):

    _inherit = 'base'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        fvg = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)

        def insert_id(doc):
            for tree in doc.xpath("//tree"):
                if not tree.xpath("/field[@name='id']"):
                    tree.insert(0, etree.Element('field', {'name': 'id'}))

        if view_type in ['tree', 'form']:
            doc = etree.XML(fvg['arch'])
            insert_id(doc)

            fvg['arch'], new_fields = self.env['ir.ui.view'].postprocess_and_fields(self._name, doc, view_id)
            # nur neue Felder uebernehmen; ansonsten gehen definierte unter views verloren (werden von form nach fields ausgelagert)
            for k, v in new_fields.items():
                if k not in fvg['fields']:
                    fvg['fields'][k] = v
        return fvg
