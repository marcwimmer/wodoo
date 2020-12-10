Provides Excel Reports:
  - either report type excel
  - or inherit from "excel.workbook"

1. Define Action:

.. code-block:: xml

   <report
    auto="False"
    id="action_xls_bom_report_excel"
    model="mrp.bom"
    name="xls_bom"
    string="BoM (Excel)"
    report_type="excel"/>

2. Define abstract class:

.. code-block:: python

    from odoo import _, api, fields, models, SUPERUSER_ID
    from odoo.exceptions import UserError, RedirectWarning, ValidationError

    class Excel(models.AbstractModel):

        _name = 'report.xls_bom'

        def excel(self, boms):
            data = {
                'sheet1': {
                    'records': recs,
                    'columns': ['col1'],
                    'model': 'mrp.bom',
                }
            }
            options = {
                'internal_column_names': False,
            }
            return data, options

2a. OR: Define abstract class and deliver excel on your own:

.. code-block:: python

    from odoo import _, api, fields, models, SUPERUSER_ID
    from odoo.exceptions import UserError, RedirectWarning, ValidationError

    class Excel(models.AbstractModel):

        _name = 'report.xls_bom'

        def excel_as_binary(self, boms):
            return <binary not base 64 encoded>

3. Colorize cells:

   * provide value in record: "__color_<fieldname>" = 'red'




Authors
------------

* Marc Wimmer <marc@itewimmer.de>

