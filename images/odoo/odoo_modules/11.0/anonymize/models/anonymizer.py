import os
from odoo import _, api, fields, models, SUPERUSER_ID
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
        name_fields = {}
        for dbfield in self.env['ir.model.fields'].search([]):
            if any(x in dbfield.name for x in [
                'phone',
                'lastname',
                'firstname',
                'city',
                'zip',
                'fax',
                'email',
            ]):
                table_name = dbfield.model_id.model.replace('.', '_')
                name_fields.setdefault(table_name, [])
                name_fields[table_name].append(dbfield.name)

        for table, fieldnames in name_fields.items():
            if not fieldnames:
                continue
            cr = self.env.cr
            cr.execute("select table_name from information_schema.tables where table_name = %s and TABLE_TYPE ='BASE TABLE'", (table,))
            if not cr.fetchone():
                continue
            cols = []
            for col in fieldnames:
                cr.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  and table_name=%s
                  and column_name=%s
                  and data_type in ('text', '"char"', 'character varying')
                """, (table, col))
                if not cr.fetchone():
                    continue
                cols.append(col)
                del col
            del fieldnames
            if not cols:
                continue

            cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              and table_name=%s
              and column_name=%s
            """, (table, 'id'))
            if not cr.fetchone():
                continue

            cr.execute("select id, {} from {} order by id desc".format(','.join(cols), table))
            recs = cr.fetchall()
            logger.info(f"Anonymizing {len(recs)} records of {table}")
            for rec in cr.fetchall():
                values = []
                for icol, col in enumerate(cols):
                    v = rec[1 + icol] or ''
                    if any(x in col for x in ['phone', 'fax']):
                        v = self.gen_phone()
                    else:
                        if "@" in v or 'email' in col:
                            v = self.generate_random_email()
                        elif col == 'lastname':
                            v = names.get_last_name()
                        elif col == 'firstname':
                            v = names.get_first_name()
                        else:
                            v = names.get_full_name()
                    values.append(v)

                sets = []
                for icol, col in enumerate(cols):
                    sets.append("{} = %s".format(col))
                cr.execute("update {} set {} where id = %s".format(table, ','.join(sets)), tuple(values + [rec[0]]))
