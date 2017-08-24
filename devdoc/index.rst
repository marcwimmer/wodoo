.. openerp suite

odoo developer documentation
==================================

Preface
==================

In Addition to code-snippets, complete workflows are explained here. Examples:

    * Report Wizard providing Criterias for Report Creation
    * Domain Terms




Domains
===================

    * x2Many - empty 
      ::
        [(field, '!=', [])]



Views
===================

Search
-----------

Fields:

    * Fields
      ::
        <field name="name" filter_domain="['|',('default_code','ilike',self),('name','ilike',self)]" />

    * Filters
      ::
        <filter name="name" string='x' domain="['|',('default_code','ilike',self),('name','ilike',self)]" />



Reporting
=================


Wizards with Criteria
-----------------------


Migration
========================


Versioning the __openerp__.py / __manifest__.py
-----------------------------------------------


        <moduledir>
        -- README.txt                      # not processed
            |-- 9.0.1.1                             # processed only on a 9.0 server
            |   |-- pre-delete_table_z.py
            |   -- foo.py                              # not processed
