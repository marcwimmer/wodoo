from odoo import models, api, _

class Product(models.Model):
    _inherit = 'product.product'

    @api.one
    def check_copy_in_translation(self):
        self.env.cr.execute("""
        select
            product_product.id
        from
            product_product inner join product_template t on t.id = product_product.product_tmpl_id
        where product_product.id = %s and product_product.product_tmpl_id in (
            select res_id from ir_translation where name like 'product.template,name'
            and (value ilike '%%copy%%' or (value ilike '%%kopie%%' and not value ilike '%%kopier%%'))
        )
        or t.name ilike '%%copy%%' or (t.name ilike '%%kopie%%' and not t.name ilike '%%kopier%%')
        """, [self.id])

        product_ids = [x[0] for x in self.env.cr.fetchall()]

        return bool(product_ids)

    @api.one
    def check_translations(self):
        self.env.cr.execute("""
            select
                id, res_id, name, lang, value
            from
                ir_translation
            where
                name = 'product.template,name'
            and
                res_id = %s
            and
                value ilike '%%(kopie)%%'
            or
                value ilike '%%(copy)%%'
        """, (self.id,))
        translations = [{
            'id': x[0],
            'name': x[2],
            'res_id': x[1],
            'lang': x[3],
            'value': x[4],
        } for x in self.env.cr.fetchall()]

        for translation in translations:
            if translation['name'] == "product.template,name":
                self.env.cr.execute("select t.name, p.default_code from product_product p inner join product_template t on p.product_tmpl_id = t.id where t.id=%s", [translation['res_id']])
                product = self.env.cr.fetchone()
                if not product:
                    continue

                name, default_code = product
                return u"Product has untranslated entries: {} {} {} {}".format(
                    translation['lang'],
                    default_code,
                    name,
                    translation['value'],
                )
        return True
