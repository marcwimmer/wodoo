import arrow
from odoo import registry
import logging
from datetime import datetime, timedelta
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.queue_job.job import Job

logger = logging.getLogger(__name__)

class QueueJob(models.Model):
    _order = 'id asc'
    _inherit = 'queue.job'

    priority = fields.Integer(group_operator='avg')
    duration = fields.Float(compute="_compute_duration", store=True)
    console_call_to_debug = fields.Char("_compute_console_call")
    create_date = fields.Datetime('Create date')

    def _compute_console_call(self):
        for self in self:
            self.console_call_to_debug = f"env['queue.job'].browse({self.id}).run_now()"

    def run_now(self):
        for self in self:
            self.ensure_one()

            job = Job.load(self.env, self.uuid)

            job.set_started()
            job.store()
            job.perform()
            job.set_done()
            job.store()

    @api.depends('date_started', 'date_done')
    def _compute_duration(self):
        for self in self:
            if not self.date_started or not self.date_done:
                self.duration = 0
                continue
            duration = (arrow.get(self.date_done) - arrow.get(self.date_started))
            self.duration = duration.seconds + duration.microseconds / 1000000

    def clear_done_jobs(self):
        # try nicht unbedingt notwendig; bei __exit__ wird ein close aufgerufen
        db_registry = registry(self.env.cr.dbname)
        with api.Environment.manage(), db_registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env.cr.execute("commit transaction;")
            sql = "delete from queue_job where state = 'done'"
            env.cr.execute(sql)
            env.cr.execute("commit transaction;")
            sql = 'vacuum full queue_job'
            env.cr.execute(sql)

    @api.constrains('exc_info')
    def _max_len_excinfo(self):
        for self in self:
            MAX = 30000
            if self.exc_info and len(self.exc_info) > MAX:
                self.exc_info = self.exc_info[:MAX]
