import os
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import names
import logging
from odoo.tools.sql import table_exists
logger = logging.getLogger(__name__)

class Destroyer(models.AbstractModel):
    _name = 'destroyer'
    _complete_clear = ['ir.attachment', 'queue.job']

    @api.model
    def _make_thin(self):
        if os.environ['DEVMODE'] != "1":
            return

        for table in Destroyer._complete_clear:
            table = table.replace(".", "_")
            if not table_exists(self.env.cr, table):
                logger.info(f"Truncating: Table {table} does not exist, continuing")
                continue
            logger.info(f"Clearing table {table}")
            self.env.cr.execute("truncate table {}".format(table))
