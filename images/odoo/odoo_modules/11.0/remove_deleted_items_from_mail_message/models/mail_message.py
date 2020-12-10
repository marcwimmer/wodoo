from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model
    def wipeout_deleted_records(self):

        self.env.cr.execute("select distinct model from mail_message;")
        for model in [x[0] for x in self.env.cr.fetchall()]:
            try:
                table = self.env[model]._table
            except Exception:
                continue
            if self.env[model]._transient:
                continue

            self.env.cr.execute("select count(*) from {table}".format(**locals()))
            count = self.env.cr.fetchone()[0]
            self.env.cr.execute("select id from {table};".format(**locals()))
            all_ids = set([x[0] for x in self.env.cr.fetchall()])
            assert len(all_ids) == count
            self.env.cr.execute("select res_id, model from mail_message where not res_id is null and model = %s;", (model, ))
            for rec in self.env.cr.fetchall():
                res_id, model = rec
                if res_id not in all_ids:
                    self.env.cr.execute("update mail_message set model = null, res_id = null where model=%s and res_id=%s", (model, res_id))
