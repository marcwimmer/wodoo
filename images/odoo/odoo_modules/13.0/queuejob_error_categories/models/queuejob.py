from odoo.addons.queue_job.job import FAILED, DONE
from .consts import severities
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class Queuejob(models.Model):
    _inherit = 'queue.job'

    severity = fields.Selection(severities, string="Severity", index=True)

    @api.model
    def _cron_calc_severity(self):
        self.env.cr.execute(
            f"update queue_job set severity = null "
            f"where state = %s and severity is not null"
        , (DONE,))
        for job in self.search([('state', '=', FAILED)]):
            self.env['queue.job.severity_rule'].apply(job)
