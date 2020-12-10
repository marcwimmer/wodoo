from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class QueueJob(models.Model):
    _inherit = 'queue.job'

    @api.model
    def requeue_terminated(self):
        self.env.cr.execute("""
            UPDATE
                queue_job
            SET
                state = 'pending'
            WHERE
                state = 'failed'
            AND
                exc_info ilike '%server closed the connection unexpectedly%'
        """)
