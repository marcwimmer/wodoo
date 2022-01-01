Move Attachments to ir.attachment
~~~~~~~~~~~~

If as_attachment=True is set for binary fields, this module checks if there
is a database field, containing data and moves it to ir.attachment.

env['migrate.attachments']._migrate_to_fs()

Authors
~~~~~~~~~~~~~~~

* Marc Wimmer <marc@itewimmer.de>

