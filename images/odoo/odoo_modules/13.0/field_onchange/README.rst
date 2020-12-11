=======================================
field_onchange
=======================================

Helps identifying field changes.

Advantage over @api.constrains:

  - transaction place of write
  - you can create records in that function (not so at api.constrains, where cache exception is thrown)

@api.onrecordchange('origin', 'field2', )
@api.one
def onchange_origin(self):
    # called at write method

@api.onfieldchange('field1', 'field2')
def onchange_field(self, changeset):
    # called at write method
    self.ensure_one()
    for field_name, values in changeset.items():
        print field_name, values['old'], values['new']

Authors
------------

* Marc Wimmer <marc@itewimmer.de>

