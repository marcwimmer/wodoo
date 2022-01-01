from odoo.addons.queue_job.job import job
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class Fields(models.Model):
    _inherit = 'ir.model.fields'

    anonymize = fields.Boolean("Anonymize")

    @api.constrains("anonymize")
    def _check_anonymize_flag(self):
        for self in self:
            if self.ttype not in ['char', 'text']:
                raise ValidationError("Only chars can be anonymized!")

    @api.model
    def _get_excluded_anonymize_models(self):
        return [
            'res.config.settings',
            'ir.property',
        ]

    @api.model
    def _apply_default_anonymize_fields(self):
        name_fields = {}
        for dbfield in self.env['ir.model.fields'].search([
            ('ttype', 'in', ['char', 'text']),
            ('model_id.model', 'not in', self._get_excluded_anonymize_models())
        ]):
            if any(x in dbfield.name for x in [
                'phone',
                'lastname',
                'firstname',
                'city',
                'zip',
                'fax',
                'mobile',
                'email',
            ]):
                self.env.cr.execute("update ir_model_fields set anonymize = true where id = %s", (dbfield.id,))

        for dbfield in self.env['ir.model.fields'].search([
            ('model', '=', 'res.partner'),
            ('name', 'in', ['display_name', 'name'])
        ]):
            self.env.cr.execute("update ir_model_fields set anonymize = true where id = %s", (dbfield.id,))
            # dbfield.anonymize = True does not work, says change through python