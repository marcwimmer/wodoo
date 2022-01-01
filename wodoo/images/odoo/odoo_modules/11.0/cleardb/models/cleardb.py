import os
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import logging
from odoo.tools.sql import table_exists
from odoo.tools import config
from odoo.modules import load_information_from_description_file
logger = logging.getLogger(__name__)

class ClearDB(models.AbstractModel):
    _name = 'frameworktools.cleardb'

    _complete_clear = [
        'queue.job', 'mail.followers', 'mail_followers_mail_message_subtype_rel',
        'bus.bus', 'auditlog.log', 'auditlog.log.line', 'mail_message', 'ir_attachment',
    ]
    _nullify_columns = [
        # 'ir.attachment:db_datas', 'ir.attachment:index_content',
    ]

    @api.model
    def _run(self):
        if os.environ['DEVMODE'] != "1":
            logger.error("Anonymization needs environment DEVMODE set.")
            return

        self.show_sizes()
        self._clear_tables()
        self._clear_fields()

        self.show_sizes()

    @api.model
    def _get_clear_tables(self):
        yield from ClearDB._complete_clear

        for model in self.env['ir.model'].search([('clear_db', '=', True)]):
            yield model.model

    @api.model
    def _get_clear_fields(self):
        yield from ClearDB._nullify_columns

        # TODO implement clear fields
        # for model in self.env['ir.model'].search([]):
        # obj = self.env.get(model.model, False)
        # if getattr(obj, 'clear_db', False):
        # yield model.model

    @api.model
    def _clear_tables(self):
        for table in self._get_clear_tables():
            table = table.replace(".", "_")
            if not table_exists(self.env.cr, table):
                logger.info(f"Truncating: Table {table} does not exist, continuing")
                continue
            logger.info(f"Clearing table {table}")
            self.env.cr.execute("truncate table {} cascade".format(table))

    def _clear_fields(self):
        for table in ClearDB._nullify_columns:
            table, field = table.split(":")
            table = table.replace(".", "_")
            if not table_exists(self.env.cr, table):
                logger.info(f"Nullifying column {field}: Table {table} does not exist, continuing")
                continue
            logger.info(f"Clearing {field} at {table}")
            self.env.cr.execute(f"update {table} set {field} = null where {field} is not null; ")

    @api.model
    def show_sizes(self):
        self.env.cr.execute("""
WITH RECURSIVE pg_inherit(inhrelid, inhparent) AS
    (select inhrelid, inhparent
    FROM pg_inherits
    UNION
    SELECT child.inhrelid, parent.inhparent
    FROM pg_inherit child, pg_inherits parent
    WHERE child.inhparent = parent.inhrelid),
pg_inherit_short AS (SELECT * FROM pg_inherit WHERE inhparent NOT IN (SELECT inhrelid FROM pg_inherit))
SELECT table_schema
    , TABLE_NAME
    , row_estimate
    , pg_size_pretty(total_bytes) AS total
    , pg_size_pretty(index_bytes) AS INDEX
    , pg_size_pretty(toast_bytes) AS toast
    , pg_size_pretty(table_bytes) AS TABLE
  FROM (
    SELECT *, total_bytes-index_bytes-COALESCE(toast_bytes,0) AS table_bytes
    FROM (
         SELECT c.oid
              , nspname AS table_schema
              , relname AS TABLE_NAME
              , SUM(c.reltuples) OVER (partition BY parent) AS row_estimate
              , SUM(pg_total_relation_size(c.oid)) OVER (partition BY parent) AS total_bytes
              , SUM(pg_indexes_size(c.oid)) OVER (partition BY parent) AS index_bytes
              , SUM(pg_total_relation_size(reltoastrelid)) OVER (partition BY parent) AS toast_bytes
              , parent
          FROM (
                SELECT pg_class.oid
                    , reltuples
                    , relname
                    , relnamespace
                    , pg_class.reltoastrelid
                    , COALESCE(inhparent, pg_class.oid) parent
                FROM pg_class
                    LEFT JOIN pg_inherit_short ON inhrelid = oid
                WHERE relkind IN ('r', 'p')
             ) c
             LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
  ) a
  WHERE oid = parent
) a
ORDER BY total_bytes DESC;
        """)
        recs = self.env.cr.fetchall()[:10]
        logger.info("Table Disk Sizes")
        for line in recs:
            print(f"{line[1]}: {line[3]}")
