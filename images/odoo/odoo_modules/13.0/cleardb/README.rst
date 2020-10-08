=======================================
cleardb
=======================================

This script is usually called with::

   odoo cleardb


To add further tables to be cleaned::

   class A(models.Model):
       _clear_db = True

After that an update of your module needs to be done.


Authors
------------

* Marc Wimmer <marc@itewimmer.de>

