from odoo import _, api, fields, models, SUPERUSER_ID, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.osv import expression
from odoo.modules.registry import Registry

class FuzzyMixin(models.AbstractModel):
    _name = 'fuzzy.mixin'

    @tools.ormcache('self')
    def _get_fuzzy_fields(self):
        def fuzzy(x):
            try:
                return x.fuzzy_search
            except AttributeError:
                return False

        return [field_name for field_name, field in self._fields.items() if fuzzy(field)]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            domains = []
            for field in self._get_fuzzy_fields():
                d = expression.AND([[(field, 'ilike', name)], args])
                domains.append(d)
            domain = expression.OR(domains)
            result = self.search(domain, limit=limit)
        else:
            result = self.search(args, limit=limit)
        result = result.name_get()
        return result

    @api.model
    def create(self, vals):
        print('create {}'.format(self._name))
        result = super().create(vals)
        result._update_fuzzy_words()
        return result

    def write(self, vals):
        result = super().write(vals)
        if any(x in vals for x in self._get_fuzzy_fields()):
            self._update_fuzzy_words()
        return result

    def unlink(self):
        self.env['fuzzy.words'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids)
        ]).unlink()
        result = super().unlink()
        return result

    def _get_fuzzy_words(self):
        result = set()

        fuzzy_fields = self._get_fuzzy_fields()
        for lang in self.env['res.lang'].sudo().search([]):
            products = self.with_context(
                    lang=lang.code,
                    prefetch_fields=False,
                    active_test=False
            ).browse(self.ids).read(fuzzy_fields)
            for product in products:
                for f in fuzzy_fields:
                    result.add(product[f])
        return list(result)

    def _update_fuzzy_words(self):
        Words = self.env['fuzzy.words'].sudo()
        Words.search([('res_model', '=', self._name), ('res_id', 'in', self.ids)]).unlink()
        for rec in self:
            fw = filter(bool, map(lambda x: (x or '').strip(), rec._get_fuzzy_words()))
            Words.create({
                'word': ' '.join(fw),
                'res_model': rec._name,
                'res_id': rec.id,
            })

            # get inherited instances, that are in other tables via inherits.
            # inherit classes are not of interest, because they are either in the same
            # table; inherit classes that have changed the _name are also not of interested:
            # they have their own store method then
            for model in Registry.model_cache.values():
                inherits = getattr(model, '_inherits', {})
                if not inherits:
                    continue
                if self._name in inherits:
                    i = self.env[model._name].sudo().with_context(active_test=False).search([(inherits[self._name], '=', rec.id)])
                    if not i:
                        continue
                    i._update_fuzzy_words()

    @api.model
    @api.returns('self',
        upgrade=lambda self, value, args, offset=0, limit=None, order=None, count=False: value if count else self.browse(value),
        downgrade=lambda self, value, args, offset=0, limit=None, order=None, count=False: value if count else value.ids)
    def search(self, args, offset=0, limit=None, order=None, count=False):

        if not self.env.context.get('no_fuzzy_search', False):
            args2 = []
            for arg in args:
                to_append = arg
                if isinstance(arg, (list, tuple)):
                    arg = list(arg)
                    if len(arg) == 3:
                        if arg[0] in self._get_fuzzy_fields() and arg[1] in ['ilike', 'like']:
                            combinations = arg[2].strip().split(" ")
                            domains = []
                            for word in combinations:
                                domains.append([('word', arg[1], word)])
                            domain = expression.AND(domains)
                            domain = expression.AND([
                                [('res_model', '=', self._name)],
                                domain,
                            ])
                            words = self.env['fuzzy.words'].sudo().search(domain)
                            ids = [x.res_id for x in words]
                            to_append = ('id', 'in', ids)

                args2.append(to_append)
            args = args2

        result = super().search(
            args,
            offset=offset, limit=limit, order=order,
            count=count
        )
        if order:
            if 'name ASC' in order or 'name DESC' in order:
                if self.env.user.lang != 'en_US':
                    result = result.with_context(lang=self.env.user.lang).sorted(lambda x: x.name, reverse='DESC' in order)
        return result
