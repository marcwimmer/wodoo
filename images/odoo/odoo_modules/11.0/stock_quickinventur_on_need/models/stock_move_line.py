from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _action_done(self):

        for rec in self:
            if rec.move_id.move_dest_ids and rec.location_dest_id.auto_inventory_on_missing_stock:
                if rec.product_id.type != 'product':
                    continue
                if rec.lot_id:
                    # check if there is negative stock
                    av = rec.product_id.with_context(
                        location=rec.location_dest_id.id,
                        lot_id=rec.lot_id.id,
                    ).qty_available
                    if av < 0:
                        self._model_make_quick_inventory(rec.location_dest_id, 0, rec.product_id, rec.lot_id)

                else:
                    pass

        result = super(StockMoveLine, self)._action_done()
        return result

    def _make_quick_inventory_on_need(self):
        for self in self.with_context(test_queue_job_no_delay=True):
            if self.state == 'assigned' and self.product_uom_qty < self.qty_done and self.qty_done > 0:
                diff = self.qty_done - self.product_uom_qty
                if diff < 0:
                    from pudb import set_trace
                    set_trace()
                self._model_make_quick_inventory(self.location_id, 0, self.product_id, self.lot_id, add=diff)
                self.product_uom_qty += diff

    @api.model
    def _model_make_quick_inventory(self, location, qty, product, lot, add=None):
        inv = self.env['stock.inventory'].create({
            "location_id": location.id,
            "filter": "lot",
            "company_id": self.env.user.company_id.id,
            "name": "Auto Quick Inventory {}: {} [{}]".format(location.name, lot.name, lot.product_id.default_code),
            "lot_id": lot.id,
        })
        inv.action_start()
        line = inv.line_ids.filtered(lambda x: x.prod_lot_id == lot)
        if line:
            line = line[0]
        else:
            line = inv.line_ids.create({
                'location_id': location.id,
                'inventory_id': inv.id,
                'prod_lot_id': lot.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
            })
        if any(line.mapped('package_id')):
            raise ValidationError(_("Packages exist for {}").format(line.product_id.default_code))
        inv.line_ids.filtered(lambda x: x.id not in line.ids).unlink()
        if not qty and add:
            line.product_qty += add
        else:
            line.product_qty = qty
        inv.action_done()

        return inv

    @api.model
    def _fix_hanging_outs(self):
        pickings = self.env['stock.picking']
        # pickings = self.env['stock.picking'].browse(471809)
        if not pickings:
            pickings = self.env['stock.picking'].search([
                ('name', 'ilike', '%OUT%'),
                ('move_lines.state', 'in', ['confirmed', 'waiting']),
                ('move_lines.move_orig_ids.state', '=', 'done'),
            ], order='id asc')

        for picking in pickings:
            moves = picking.move_lines.filtered(lambda x: x.reserved_availability < x.product_uom_qty)
            print(picking.name)
            for move in moves:
                if move.move_orig_ids.state == 'done':
                    av = move.product_id.with_context(
                        location=move.location_id.id,
                        lot_id=move.move_orig_ids.move_line_ids.lot_id.id
                    ).read(['qty_available'])[0]['qty_available']

                    if av < 0:
                        self._model_make_quick_inventory(
                            move.location_id,
                            0,
                            move.move_orig_ids.mapped('move_line_ids').product_id,
                            move.move_orig_ids.mapped('move_line_ids').lot_id,
                        )
                    av_not_res = move.product_id.with_context(
                        location=move.location_id.id,
                        lot_id=move.move_orig_ids.move_line_ids.lot_id.id
                    ).qty_available_not_res

                    if av_not_res < move.product_uom_qty:
                        self._model_make_quick_inventory(
                            move.location_id,
                            0,
                            move.move_orig_ids.mapped('move_line_ids').product_id,
                            move.move_orig_ids.mapped('move_line_ids').lot_id,
                            add=move.move_orig_ids.product_uom_qty - av_not_res,
                        )
                    move._action_assign()
                    assert move.state == 'assigned'
                    assert move.move_line_ids.mapped('lot_id') == move.move_orig_ids.mapped('move_line_ids.lot_id')
                    self.env.cr.commit()
