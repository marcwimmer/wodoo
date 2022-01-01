import traceback
from odoo import _, api, fields, models, SUPERUSER_ID, registry
import threading
class Base(models.Model):
    _inherit = 'ir.ui.view'

    @api.one
    def migration_delete_view(self):

        self.search([('inherit_id', '=', self.id)]).migration_delete_view()
        self.unlink()

    @api.model
    def kill_faulty_views(self, on_faulty, domain=[]):
        all_views = self.env['ir.ui.view'].with_prefetch().search(domain)
        inherited_views = all_views.filtered(lambda v: v.mode != 'primary')
        primary_views = all_views.filtered(lambda v: v.mode == 'primary')

        faulties = []

        models = all_views.mapped('model')
        for P1, model in enumerate(models):
            if not model:
                continue
            print("find faulty view", model, P1, 'of', len(models))
            for primary_view in primary_views.filtered(lambda x: x.model == model):
                try:
                    primary_view.read_combined()
                except Exception:
                    print("faulty found in primary inheritance tree - detecting it")
                    views = inherited_views.filtered(lambda x: x.model == model and x.type == primary_view.type)
                    for i2, view in enumerate(views):
                        print('sub', i2, len(views))
                        try:
                            view.read_combined()
                        except Exception:
                            print("Faulty view is ", view.id, ' at ', model)
                            faulties.append(view.id)
                            msg = traceback.format_exc()
                            print(msg)

        for view in faulties:
            view = self.env.browse(view)
            if not on_faulty:
                view.unlink()
            else:
                on_faulty(view)
