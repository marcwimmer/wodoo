import re
from .consts import severities
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class SeverityRules(models.Model):
    _order = 'priority'
    _name = 'queue.job.severity_rule'

    priority = fields.Integer("Prio")
    severity = fields.Selection(severities)
    regex = fields.Boolean("Is Regex")

    text_in_exception = fields.Char("Text in Exception")

    @api.model
    def apply(self, job):
        for rule in self.search([]):
            if rule.applies(job):
                self.severity = rule.severity
                break

    def applies(self, job):
        exc = job.exc_info or ''
        if self.regex:
            if re.findall(self.text_in_exception, exc):
                return True
            elif self.text_in_exception in exc:
                return True
        return False
