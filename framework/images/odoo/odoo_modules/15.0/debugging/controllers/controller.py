from odoo import http
from odoo.http import request

class DebugController(http.Controller):

    @http.route(['/xmlids', '/xmlids/<model>'], auth='public', type="http")
    def handler(self, **post):
        datas = request.env['ir.model.data'].sudo().search([])

        model = post.get('model')
        by_model = {}
        for data in datas:
            if model:
                if data.model != model:
                    continue
            by_model.setdefault(data.model, [])
            by_model[data.model].append({
                'name': f"{data.module}.{data.name}"
            })

        return request.render('debugging.vxmlids', {
            'by_model': by_model
        })