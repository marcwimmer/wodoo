from odoo import _, api, models, SUPERUSER_ID
from inspect import getmembers
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Base(models.AbstractModel):
    _inherit = 'base'

    @classmethod
    def _init_constraints_onchanges(cls):
        super()._init_constraints_onchanges()
        cls._recordchange_methods = Base._recordchange_methods
        cls._fieldchange_methods = Base._fieldchange_methods

    @property
    def _recordchange_methods(self):
        def is_constraint(func):
            return callable(func) and hasattr(func, '_recordchange')

        cls = type(self)
        methods = []
        for attr, func in getmembers(cls, is_constraint):
            for name in func._recordchange:
                field = cls._fields.get(name)
                if not field:
                    raise Exception("method %s.%s: @recordchange parameter %r is not a field name", cls._name, attr, name)
                elif not (field.store or field.inverse or field.inherited):
                    raise Exception("method %s.%s: @recordchange parameter %r is not writeable", cls._name, attr, name)
            methods.append(func)

        # optimization: memoize result on cls, it will not be recomputed
        cls._recordchange_methods = methods
        return methods

    @property
    def _fieldchange_methods(self):
        def is_constraint(func):
            return callable(func) and hasattr(func, '_fieldchange')

        cls = type(self)
        methods = []
        for attr, func in getmembers(cls, is_constraint):
            for name in func._fieldchange:
                field = cls._fields.get(name)
                if not field:
                    raise Exception("method %s.%s: @fieldchange parameter %r is not a field name", cls._name, attr, name)
                elif not (field.store or field.inverse or field.inherited):
                    raise Exception("method %s.%s: @fieldchange parameter %r is not writeable", cls._name, attr, name)
            methods.append(func)

        # optimization: memoize result on cls, it will not be recomputed
        cls._fieldchange_methods = methods
        return methods

    def _get_tracked_fields_recordchange(self):
        for m in self._recordchange_methods:
            yield from m._recordchange
        for m in self._fieldchange_methods:
            yield from m._fieldchange

    def trigger_field_change(self, changesets):
        methods = [x for x in self._fieldchange_methods if any(field_name in x._fieldchange for field_name in changesets.keys())]
        for method in methods:
            method_changeset = {}
            for field_name, values in changesets.items():
                if field_name in method._fieldchange:
                    method_changeset[field_name] = values
            method(self, method_changeset)

    def trigger_record_change(self, fields):
        methods = [x for x in self._recordchange_methods if any(f in fields for f in x._recordchange)]
        for method in methods:
            method(self)

    def write(self, vals):
        tracked_fields = list(self._get_tracked_fields_recordchange()) or []
        if tracked_fields:
            before = {}
            for rec in self:
                before.setdefault(rec.id, {})
                for field in tracked_fields:
                    before[rec.id][field] = rec[field]

        result = super().write(vals)

        if tracked_fields:
            after = {}
            for rec in self:
                after.setdefault(rec.id, {})
                for field in tracked_fields:
                    after[rec.id][field] = rec[field]

            for rec in self:
                changed_fields = []
                a = after[rec.id]
                b = before[rec.id]
                changeset = {}
                for field in tracked_fields:
                    if a[field] != b[field]:
                        changed_fields.append(field)
                        changeset[field] = {
                            'new': a[field],
                            'old': b[field],
                        }
                rec.trigger_field_change(changeset)
                rec.trigger_record_change(changed_fields)

        return result
