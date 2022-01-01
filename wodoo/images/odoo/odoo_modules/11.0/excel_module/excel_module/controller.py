import base64
from odoo import http
from odoo.http import request
from odoo.http import content_disposition

class ExcelReportController(http.Controller):

    @http.route('/excel_report/<report_name>', auth='user', type="http")
    def get_excel_report(self, report_name, model, res_id, **post):
        try:
            res_id = int(res_id)
        except Exception:
            if ',' in res_id:
                res_id = res_id.split(',')
                res_id = [int(x) for x in res_id]

        report = request.env['ir.actions.report'].sudo().search([
            ('report_name', '=', report_name),
        ])
        if report.report_type != 'excel':
            return

        if not model:
            model = report.model

        records = request.env[model].browse(res_id)
        report_object = request.env['report.' + report_name]
        if getattr(report_object, 'excel_as_binary', False):
            content = report_object.excel_as_binary(records)
        else:
            RES = report_object.excel(records)
            if isinstance(RES, dict):
                RES = (RES, {})
            if len(RES) != 2:
                raise Exception("Please return (data, options) as tuple.")
            data, options = RES
            assert isinstance(data, dict), "Returned Data must be of type dict!"
            content = request.env['excel.maker'].create_excel(request.env, data, **options)

        name = report.print_report_name or report_name + '.xlsx'
        return http.request.make_response(content, [
            ('Content-Type', 'application/octet-stream; charset=binary'),
            ('Content-Disposition', content_disposition(name))
        ])
