from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class RequeueOptions(models.Model):
    _inherit = 'queue.job.function'

    requeue_on_failed = fields.Boolean("Requeue on failed")

    @api.model
    def cron_requeue(self):
        self.env.cr.execute("""
            update
                queue_job
            set
                state = 'pending'
            where
                state = 'failed'
            and
                coalesce((select requeue_on_failed from queue_job_function f where f.id = queue_job.job_function_id), false) = true
            ;
        """)
