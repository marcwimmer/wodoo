import time
import base64
import excel
import threading
from openerp.report.report_sxw import report_sxw
from openerp.modules.registry import RegistryManager
from openerp.addons.excel_module import report_engine

old_create = None
def create(self, cr, uid, ids, data, context=None):
    if data and data.get('report_type', False) == 'excel':
        pool = RegistryManager.get(cr.dbname)
        Reps = pool["ir.actions.report.xml"]
        report_ids = Reps.search(cr, 1, [('report_name', '=', self.name2)])
        report = Reps.browse(cr, 1, report_ids, context=context)[0]

        result = old_create(self, cr, uid, ids, data, context=context)

        user = pool['res.users'].browse(cr, 1, uid, context=context)
        email = user.partner_id.email

        mail_id = pool["mail.mail"].create(cr, uid, {
            'auto_delete': True,
            'subject': u"Report {}".format(report.name),
            'body_html': "Find the report attached",
            'email_to': email,
        }, context=context)

        if report.attachment:
            obj = None
            if data.get('ids', False):
                pool = self.pool[report['model']]
                obj = pool.browse(cr, 1, data['ids'][0])
                if obj:
                    obj = obj[0]
            else:
                try:
                    obj = pool[context['active_model']].browse(cr, 1, context['active_id'])
                except Exception:
                    pass
            aname = eval(report.attachment, {'object': obj, 'time': time})
        else:
            aname = u'{}.xlsx'.format(report.name)

        if not aname.endswith(".xlsx"):
            aname += u'.xlsx'

        pool['ir.attachment'].create(cr, uid, {
            'name': aname,
            'datas': base64.b64encode(result[0]),
            'res_model': 'mail.mail',
            'res_id': mail_id,
        }, context=context)
        pool["mail.mail"].send(cr, uid, [mail_id])

        return result
    else:
        result = old_create(self, cr, uid, ids, data, context=context)
        return result


old_create = report_sxw.create
report_sxw.create = create
