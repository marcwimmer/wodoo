=======================================
field_onchange
=======================================

Helps identifying field changes.

Add to your server_wide_modules:
server_wide_modules = web,field_onchange,queue_job


Advantage over @api.constrains:

  - transaction place of write
  - you can create records in that function (not so at api.constrains, where cache exception is thrown)

Sample::

     @api.recordchange('origin', 'field2', )
     @api.one
     def onchange_origin(self):
         # called at write method

     @api.fieldchange('field1', 'field2')
     @api.one
     def onchange_field(self, changeset):
         # called at write method
         self.ensure_one()
         for field_name, values in changeset.items():
             print(field_name, values['old'], values['new'])

Authors
------------

* Marc Wimmer <marc@itewimmer.de>

