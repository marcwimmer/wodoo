# adds compare functions to compare dict values against database entries

from odoo.fields import Field
from odoo import models

def compare_field(self, db_value, dict_value):
    if self.type == 'many2many':
        dict_value = dict_value or []
        for el in dict_value:
            if el[0] == 6 and len(dict_value) == 1:
                return set(dict_value[0][2]) == set(db_value.ids)
        if any(x[0] in (1, 2, 3, 4, 5) for x in dict_value):
            return False

        return True

    elif self.type == 'one2many':
        dict_value = dict_value or []
        if any(x[0] in (0, 2) for x in dict_value):
            return False
        return True
    elif self.type == 'many2one':
        if dict_value:
            return not dict_value and not db_value
        return db_value.id == dict_value
    elif self.type in ['monetary', 'float', 'integer']:
        if not db_value and not dict_value:
            return True
        else:
            return db_value == dict_value
    elif self.type in ['date']:
        # 1980-04-04 23:23:23 --> 1980-04-04
        if dict_value and len(dict_value) > 10:
            dict_value = dict_value[:10]
        return db_value == dict_value
    else:
        return db_value == dict_value

class Base(models.AbstractModel):
    _inherit = 'base'

    def compare_dict(self, values):
        """
        Compares record against values.
        If differs, then list differing is filled up.
        """
        self.ensure_one()
        diff = {}
        for k, v in values.items():
            if not self._fields[k].compare_field(self[k], v):
                diff[k] = v

        return diff

Field.compare_field = compare_field
