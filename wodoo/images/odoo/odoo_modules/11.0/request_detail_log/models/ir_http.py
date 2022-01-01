import json
import logging
import traceback
from datetime import datetime
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.http import request, STATIC_CACHE, content_disposition
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo import registry
_logger = logging.getLogger(__name__)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(self):
        start = datetime.now()
        do_log = request.env.ref('request_detail_log.enabled').sudo().value == '1'
        result = super()._dispatch()

        end = datetime.now()

        seconds = (end - start).total_seconds()
        if do_log:
            url = request.httprequest.url

            def format_url(url):
                texts = [url]
                LEN = 100
                while len(texts[-1]) > LEN:
                    text = texts[-1][LEN:]
                    texts[-1] = texts[-1][:LEN]
                    texts.append(text)
                return '\n'.join(texts)

            url = format_url(url)

            if 'longpolling' not in url and isinstance(request.params, dict):
                try:
                    args = json.dumps(request.params, indent=4)
                except Exception:
                    msg = traceback.format_exc()
                    _logger.warn(msg)
                else:
                    method = request.params.get('method', False)
                    model = request.params.get('model', False)

                    # try nicht unbedingt notwendig; bei __exit__ wird ein close aufgerufen
                    with registry(request.env.cr.dbname).cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        env['log.request'].sudo().create({
                            'user_id': request.env.user.id,
                            'url': url,
                            'duration': seconds,
                            'args': args,
                            'method': method,
                            'model': model,
                        })
                        cr.commit()

        return result
