import os
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.tools.sql import column_exists
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import random
import logging
logger = logging.getLogger(__name__)


class Anonymizer(models.AbstractModel):
    _name = 'frameworktools.anonymizer'
    _domains = ["hotmail.com", "gmail.com", "aol.com", "mail.com", "mail.kz", "yahoo.com"]

    @api.model
    def gen_phone(self):
        first = str(random.randint(00000, 99999))
        second = str(random.randint(10000, 99999)).zfill(7)

        last = (str(random.randint(1, 99)).zfill(2))
        while last in ['1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888']:
            last = (str(random.randint(1, 9998)).zfill(4))

        return '{}/{}-{}'.format(first, second, last)

    @api.model
    def get_one_random_domain(self, domains):
        return random.choice(domains)

    @api.model
    def generate_random_email(self):
        import names
        return names.get_full_name().replace(' ', '.') + "@" + self.get_one_random_domain(self._domains)

    def _delete_mail_tracking_values(self):
        for field in self.env['ir.model.fields'].search([
            ('anonymize', '=', True)
        ]):
            self.env.cr.execute("""
                delete from mail_tracking_value where field = %s"
                and
                mail_message_id in (select id from mail_message where model=%s)
            """, (field.name, field.model_id.model))

    @api.model
    def _delete_critical_tables(self):
        self.env.cr.execute("delete from mail_mail;")

    @api.model
    def _run(self):
        if os.environ['DEVMODE'] != "1":
            return
        import names

        self.env['ir.model.fields']._apply_default_anonymize_fields()
        self._delete_critical_tables()
        self._delete_mail_tracking_values()

        KEY = 'db.anonymized'
        if self.env['ir.config_parameter'].get_param(key=KEY, default='0') == '1':
            return

        for field in self.env['ir.model.fields'].search([('anonymize', '=', True)]):
            try:
                obj = self.env[field.model]
            except KeyError:
                continue
            table = obj._table
            cr = self.env.cr
            cr.execute("select table_name from information_schema.tables where table_name = %s and TABLE_TYPE ='BASE TABLE'", (table,))
            if not cr.fetchone():
                continue
            if not column_exists(cr, table, field.name):
                logger.info(f"Ignoring not existent column: {table}:{field.name}")
                continue

            cr.execute(f"select id, {field.name} from {table} order by id desc")
            recs = cr.fetchall()
            logger.info(f"Anonymizing {len(recs)} records of {table}")
            for rec in recs:
                v = rec[1] or ''
                if any(x in field.name for x in ['phone', 'fax', 'mobile']):
                    v = self.gen_phone()
                else:
                    if "@" in v or 'email' in field.name:
                        v = self.generate_random_email()
                    elif field.name == 'lastname':
                        v = names.get_last_name()
                    elif field.name == 'firstname':
                        v = names.get_first_name()
                    else:
                        v = names.get_full_name()

                cr.execute(f"update {table} set {field.name} = %s where id = %s", (
                    v,
                    rec[0],
                ))

        self.env['ir.config_parameter'].set_param(KEY, '1')