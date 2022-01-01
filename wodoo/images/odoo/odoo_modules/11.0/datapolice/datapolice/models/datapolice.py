from odoo import models, fields, api, _
import base64
from pathlib import Path
import tempfile
import traceback
from datetime import datetime
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class DataPolice(models.Model):
    _name = 'data.police'

    active = fields.Boolean(default=True)
    name = fields.Char('Name', size=256, required=True, translate=True)
    checkdef = fields.Char('Def to call', size=128, required=False)
    fixdef = fields.Char('Def to fix error', size=128, required=False)
    expr = fields.Text("Expression (using obj)", )
    model = fields.Char('Model', size=128, required=True)
    src_model = fields.Char("Source Model", help="if given, then the checkdef is called at this model. Expects erroneous items of type 'model'")
    enabled = fields.Boolean("Enabled", default=True)
    errors = fields.Integer("Count Errors")
    domain = fields.Text('Domain')
    recipients = fields.Char("Mail-Recipients", size=1024)
    user_ids = fields.Many2many('res.users', string="Recipients (users)")
    last_errors = fields.Text("Last Error Log")

    def toggle_active(self):
        self.active = not self.active

    @api.constrains("src_model", "domain", "checkdef", "expr")
    @api.one
    def check_model_domain(self):
        if self.domain and self.src_model:
            raise ValidationError("Either provide src_model OR domain")
        if not self.checkdef and not self.expr:
            raise ValidationError("Either provide expression or check-function")

    @api.multi
    def run_fix(self):
        self.ensure_one()
        if not self.fixdef:
            return

        self.with_context(datapolice_run_fixdef=True).run()

    @api.model
    def create(self, values):
        if 'def' in values.keys():
            raise Exception("Please use checkdef instead of def!!!")
        if 'recipients' in values:
            if values['recipients']:
                values['recipients'] = values['recipients'].replace(",", ";").replace(" ", "")
        result = super(DataPolice, self).create(values)
        return result

    @api.multi
    def write(self, values):
        if 'recipients' in values:
            if values['recipients']:
                values['recipients'] = values['recipients'].replace(",", ";").replace(" ", "")
        result = super(DataPolice, self).write(values)
        return result

    @api.multi
    def run(self):
        if not self:
            self = self.search([('enabled', '=', True)])

        all_errors = {}

        def format(x):
            try:
                if not ('model' in x and 'res_id'):
                    raise Exception()
            except Exception:
                return str(x)
            else:
                return u'{}#{}: {}'.format(
                    x['model'],
                    x['res_id'],
                    x['text'],
                )

        for dp in self:
            obj = self.env[dp.model]
            errors = []
            try:
                if dp.src_model and dp.checkdef:
                    objects = getattr(self.env[dp.src_model], dp.checkdef)().with_context(prefetch_fields=False)
                else:
                    objects = obj.with_context(active_test=False, prefetch_fields=False).search(dp.domain and eval(dp.domain) or [])
            except Exception:
                if self.env.context.get('from_ui', False):
                    raise
                objects = []
                msg = traceback.format_exc()
                errors.append({
                    'res_id': 0,
                    'res_model': dp.model,
                    'text': msg,
                })

            for idx, obj in enumerate(objects):
                self._logger.debug("Checking {} {} of {}".format(dp.name, idx + 1, len(objects)))
                instance_name = "n/a"
                instance_name = self.env["data.police.formatter"].do_format(obj)

                def run_check():
                    exception = ""
                    result = False
                    self = obj  # for the expression # NOQA

                    if dp.expr:
                        try:
                            result = eval(dp.expr)
                        except Exception as e:
                            exception = str(e)
                    else:
                        try:
                            result = getattr(obj, dp.checkdef)()
                            if isinstance(result, list) and len(result) == 1:
                                if isinstance(result[0], bool):
                                    # [True] by @api.one
                                    result = result[0]
                                elif result[0] is None:
                                    result = True
                        except Exception as e:
                            exception = str(e)

                    not_ok = result is False or (result and not (result is True)) or exception
                    if not exception and isinstance(result, str):
                        exception = result

                    return {
                        'ok': not not_ok,
                        'exception': exception,
                    }

                if dp.src_model:
                    ok = {
                        'ok': False,
                        'exception': False,
                    }
                else:
                    ok = run_check()

                    if not ok['ok']:

                        if dp.fixdef:
                            fixed = False
                            try:
                                getattr(obj, dp.fixdef)()
                                fixed = True
                            except Exception:
                                msg = traceback.format_exc()
                                self._logger.error(msg)

                            if fixed:
                                ok = run_check()

                if not ok['ok']:
                    text = u"; ".join(x for x in [instance_name, ok.get('exception', '') or ''] if x)
                    errors += [{
                        'model': obj._name,
                        'res_id': obj.id,
                        'text': text,
                    }]
                    try:
                        self._logger.error(u"Data Police {}: not ok at {} {} {}".format(dp.name, obj._name, obj.id, text))
                    except Exception:
                        pass

            dp.write({'errors': len(errors)})
            all_errors[dp] = errors
            dp.write({'last_errors': '\n'.join(format(x) for x in errors)})

        def str2mails(s):
            s = s or ''
            s = s.replace(",", ";")
            return [x.lower() for x in s.split(";") if x]

        dps = all_errors.keys()

        dp_recipients = []
        for dp in dps:
            if dp.recipients:
                dp_recipients += str2mails(dp.recipients)
            if dp.user_ids:
                dp_recipients += [x.lower() for x in dp.user_ids.mapped('email') if x]

        mail_to = ','.join(set(dp_recipients))

        text = ""
        for dp in dps:
            errors = all_errors[dp]
            if not errors:
                continue
            text += u"<h2>{}</h2>".format(dp.name)
            text += "<ul>"
            small_text = text
            for i, error in enumerate(sorted(errors, key=lambda e: (e.get('model', False), e.get('res_id', False)), reverse=True)):
                if 'model' in error and 'res_id' in error:
                    url = self.env['ir.config_parameter'].get_param('web.base.url')
                    url += "#model=" + error['model'] + "&id=" + str(error['res_id'])
                    link = u"<a href='{}'>{}</a>".format(url, error['text'])
                    appendix = u"<li>{}</li>\n".format(link)
                else:
                    appendix = u"<li>{}</li>\n".format(error)
                text += appendix
                if i < 50:
                    small_text += appendix

            text += "</ul>"
            small_text += "</ul>"

        if text:

            text = base64.encodestring(text.encode("utf-8"))
            self.env["mail.mail"].create({
                'auto_delete': True,
                'subject': 'DataPolice Run {}'.format(datetime.now().strftime("%Y-%m-%d")),
                'body_html': small_text,
                'body': small_text,
                'email_to': mail_to,
                'attachment_ids': [[0, 0, {
                    'datas': text,
                    'datas_fname': 'data_police.html',
                    'name': 'data_police.html',
                }]
                ],
            }).send()

        return True
