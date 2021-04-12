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

    @api.model
    def _run(self):
        if os.environ['DEVMODE'] != "1":
            return
        import names

        self.env['ir.model.fields']._apply_default_anonymize_fields()

        for field in self.env['ir.model.fields'].search([('anonymize', '=', True)]):
            try:
                obj = self.env[field.model]
            except KeyError:
                continue
            table = obj._table
            cr = self.env.cr
            if not column_exists(cr, table, field.name):
                logger.info(f"Ignoring not existent column: {table}:{field.name}")
                continue

            cr.execute(f"select id, {field.name} from {table} order by id desc")
            recs = cr.fetchall()
            logger.info(f"Anonymizing {len(recs)} records of {table}")
            for rec in recs:
                v = rec[1] or ''
                if any(x in field.name for x in ['phone', 'fax']):
                    v = self.gen_phone()
                elif "@" in v or 'email' in field.name:
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
