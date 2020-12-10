from odoo.addons import decimal_precision as dp
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.queue_job.job import job
# env['stock.quant'].fix_quantity(); env.cr.commit()
class StockQuant(models.Model):
    _inherit = 'stock.quant'

    calculated_reservations = fields.Float(compute="_compute_calculated_reservations", store=False)
    needs_fix_reservation = fields.Boolean(compute="_compute_calculated_reservations", store=False)
    over_reservation = fields.Boolean(compute="_compute_over_reservation", store=True)

    @api.depends("quantity", "reserved_quantity")
    def _compute_over_reservation(self):
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        for self in self:
            self.over_reservation = round(self.reserved_quantity, digits) > round(self.quantity, digits)

    @api.constrains("reserved_quantity", "quantity")
    def _check_over_reservation(self):
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        for self in self:
            if self.location_id.usage == 'internal':
                if round(self.quantity, digits) < round(self.reserved_quantity, digits):
                    raise ValidationError(_("Cannot reserve {} for {}. Available {}.").format(
                        self.reserved_quantity,
                        self.product_id.default_code,
                        self.quantity,
                    ))

    def _compute_calculated_reservations(self):
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        for self in self:
            self.env.cr.execute("""
                select sum(l.product_uom_qty), l.product_uom_id, pt.uom_id
                from stock_move_line l
                inner join stock_move m
                on m.id = l.move_id
                inner join product_product p
                on p.id = l.product_id
                inner join product_template pt
                on pt.id = p.product_tmpl_id
                where l.location_id=%s
                and coalesce(lot_id, 0) =%s
                and l.product_id=%s
                and m.state in ('assigned', 'partially_available')
                group by l.product_uom_id, pt.uom_id
            """, (self.location_id.id, self.lot_id.id or 0, self.product_id.id))
            Uom = self.env['product.uom']

            def convert(x):
                qty, uom_id, product_uom_id = x
                qty = round(Uom.browse(uom_id)._compute_quantity(qty, Uom.browse(product_uom_id), rounding_method='HALF-UP'), digits)
                return qty, uom_id, product_uom_id

            sums = [convert(x) for x in self.env.cr.fetchall()]
            self.calculated_reservations = sum(x[0] for x in sums)
            self.needs_fix_reservation = self.calculated_reservations != self.reserved_quantity

    @job
    def fix_reservation(self):
        for self in self:
            if self.reserved_quantity != self.calculated_reservations:
                self.sudo().reserved_quantity = self.calculated_reservations
        self._merge_quants()

    @api.model
    def _fix_all_reservations(self):
        for product in self.env['product.product'].search([('type', '=', 'product')]):
            q = self.env['stock.quant'].search([('product_id', '=', product.id)], order='id desc').with_context(prefetch_fields=False)
            q.with_delay().fix_reservation()

    @api.model
    def _get_status(self, fix, product=None, raise_error=False, expects_stock_at_location=0):
        products = product or self.env['product.product'].search([('type', '=', 'product')])
        for product in products:
            for lot in self.env['stock.production.lot'].search([('product_id', '=', product.id)]):

                self.env.cr.execute("""
                    select sum(product_uom_qty), stock_move_line.location_id, lot_id
                    from stock_move_line
                    inner join stock_location l
                    on l.id = stock_move_line.location_id
                    where lot_id=%s
                    and state in ('assigned', 'partially_available')
                    and l.usage in ('internal')
                    group by stock_move_line.location_id, lot_id
                """, (lot.id,))
                sums = self.env.cr.fetchall()

                # missing the quant for zero stock but reserved
                if not [x for x in sums if x[1] == expects_stock_at_location]:
                    sums += [(0, expects_stock_at_location, lot.id)]

                for S in sums:
                    tries = 0
                    while True:
                        tries += 1

                        self.env.cr.execute("""
                            select reserved_quantity
                            from stock_quant
                            where lot_id=%s and location_id=%s
                        """, (lot.id, S[1]))
                        quants = self.env.cr.fetchall()
                        if len(quants) > 1:
                            if tries > 1:
                                raise Exception(f"Cannot merge duplicate quants {product.default_code}")
                            self._merge_quants()
                        else:
                            break
                    if len(quants) == 0 and S[0]:
                        error = f"Quant missing: {product.default_code}-{lot.name}"
                        if raise_error:
                            raise UserError(error)
                        if fix:
                            self._fix_missing_quant(lot=lot, location_id=S[1], quantity=S[0])

                    elif quants and quants[0][0] != S[0]:
                        error = f"Reservation deviation: {product.default_code}-{lot.name}"
                        if raise_error: raise UserError(error)
                        if fix:
                            self.fix_reservation()
            self.env.cr.commit()

    def _fix_missing_quant(self, lot, location_id, quantity):
        location = self.env['stock.location'].browse(location_id)
        inv = self.env['stock.inventory'].create({
            "location_id": location.id,
            "filter": "lot",
            "company_id": self.env.user.company_id.id,
            "name": "Fix Quant Inventory {}: {} [{}]".format(location.name, lot.name, lot.product_id.default_code),
            "lot_id": lot.id,
        })
        inv.action_start()
        line = inv.line_ids.filtered(lambda x: x.prod_lot_id == lot and x.location_id == location_id)
        if line:
            quantity += line.product_qty

        inv.line_ids.unlink()
        inv.line_ids = [[0, 0, {
            'prod_lot_id': lot.id,
            'product_id': lot.product_id.id,
            'location_id': location.id,
            'product_qty': quantity,
        }]]
        inv.action_done()

        # also still broken after that
        self.env['stock.quant'].search([('lot_id', '=', lot.id)]).fix_reservation()

        return inv

    # @api.model
    # def _fix_result_package_id(self, filter=None):
        # for q in self.env['stock.quant'].search(filter or [], order='id desc'):
            # print("checking ", q.id)
            # package = q.package_id
            # falsy = package.quant_ids.filtered(lambda x: x.location_id != q.location_id)
            # if falsy:
                # package.quant_ids = [[3, x.id] for x in falsy]
                # print("Fixed falsy packages")
                # self.env.cr.commit()
