from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import json
class LogRequest(models.Model):
    _name = 'log.request'
    _order = 'date desc'
    _clear_db = True

    url = fields.Char("Url")
    url_display = fields.Text("Url", compute="_compute_url_display", store=True)
    user_id = fields.Many2one('res.users')
    model = fields.Char("Model")
    method = fields.Char("Method")
    duration = fields.Float("Duration [s]", group_operator="avg")
    duration_min = fields.Float("Duration [s] max", group_operator="max", store=True, compute="_compute_minmax")
    duration_max = fields.Float("Duration [s] min", group_operator="min", store=True, compute="_compute_minmax")
    date = fields.Datetime("Date", default=lambda self: fields.Datetime.now())
    args = fields.Text("Args")

    @api.constrains("args")
    def _check_critical_info(self):
        REPLACETEXT = 'contains confidential data'
        for self in self:
            if not self.args:
                continue
            if 'password' in self.args:
                try:
                    data = json.loads(self.args)
                    if 'password' not in data:
                        self.args = REPLACETEXT
                    else:
                        if data['password'] != REPLACETEXT:
                            data['password'] = REPLACETEXT
                            self.args = json.dumps(data)
                except Exception:
                    self.args = REPLACETEXT

    @api.depends('duration')
    @api.one
    def _compute_minmax(self):
        self.duration_min = self.duration
        self.duration_max = self.duration

    @api.depends('url')
    @api.one
    def _compute_url_display(self):
        # texts = [self.url or '']
        # LEN = 40
        self.url_display = (self.url or '')[:80]
        return
        # while len(texts[-1]) > LEN:
        # text = texts[-1][LEN:]
        # texts[-1] = texts[-1][:LEN]
        # texts.append(text)
        # self.url_display = '\n'.join(texts)
