import arrow
from odoo.addons import decimal_precision as dp
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.addons.queue_job.job import job
# env['stock.quant'].fix_quantity(); env.cr.commit()
class StockQuant(models.Model):
    _inherit = 'stock.quant'

    calculated_reservations = fields.Float(compute="_compute_calculated_reservations", store=False)
    needs_fix_reservation = fields.Boolean(compute="_compute_calculated_reservations", store=False, search="_search_needs_fix")
    over_reservation = fields.Boolean(compute="_compute_over_reservation", store=True)

    @api.depends("quantity", "reserved_quantity")
    def _compute_over_reservation(self):
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        for self in self:
            self.over_reservation = round(self.reserved_quantity, digits) > round(self.quantity, digits)

    def _check_stock_quants(self, products):
        breakpoint()
        quants = self.search([
            ('product_id', 'in', products.ids),
            ('needs_fix_reservation', '=', True),
        ])
        job_priority = int(self.env['ir.config_parameter'].get_param(key="fix_reservations.priority", default="2"))
        job_channel = self.env['ir.config_parameter'].get_param(key="fix_reservations.channel", default="fix_reservations")
        job_shift_minutes = self.env['ir.config_parameter'].get_param(key="fix_reservations.shift_minutes", default="10")
        quants.with_delay(
            eta=arrow.get().shift(minutes=int(job_shift_minutes)).datetime,
            channel=job_channel,
            priority=job_priority,
        ).fix_reservation()

    def _get_quant_deviations(self, product_id):
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        if product_id:
            self.env.cr.execute("select id into temporary table _filter_products from product_product where id=%s;", (product_id,))
        else:
            self.env.cr.execute("select id into temporary table _filter_products from product_product")

        self.env.cr.execute("""
            select
                sm.product_id,
                l.location_id,
                l.lot_id,
                sum(l.product_qty)
            from
                stock_move_line l
            inner join
                stock_move sm
            on
                sm.id = l.move_id
            inner join
                stock_location loc
            on
                loc.id = l.location_id
            inner join
                product_product pp
            on
                pp.id = l.product_id
            inner join
                product_template pt
            on
                pt.id = pp.product_tmpl_id
            where
                sm.state in ('assigned', 'partially_available')
            and
                loc.usage = 'internal'
            and
                pt.type = 'product'

            group by
                sm.product_id, l.location_id, l.lot_id
            order by
                1, 2, 3

        """, (
            product_id, product_id
        ))
        ids = []
        for rec in self.env.cr.fetchall():
            product_id, location_id, lot_id, qty = rec
            self.env.cr.execute("""
                select sum(reserved_quantity)
                from stock_quant
                where
                    product_id=%s
                and
                    location_id=%s
                and
                    coalesce(lot_id, 0) = %s
            """.format(digits), (
                product_id,
                location_id,
                lot_id or 0
            ))
            qty2 = self.env.cr.fetchone()[0]
            if qty2 is None and qty:
                breakpoint()
                lot = self.env['stock.production.lot'].browse(lot_id)
                print(f"inventory {lot.product_id.default_code} {lot.name}")
                lot = self.env['stock.production.lot'].browse(lot_id)
                self._fix_missing_quant(
                    lot,
                    self.env['product.product'].browse(product_id),
                    location_id,
                    round(qty, digits)
                )
            elif round(qty2 or 0.0, digits) != round(qty or 0.0, digits):
                ids += [product_id]
        self.env.cr.execute("drop table _filter_products;")
        return ids

    def _search_needs_fix(self, operator, value):
        product_ids = self._get_quant_deviations(None)
        ids = self.search([
            ('location_id.usage', '=', 'internal'),
            ('product_id', 'in', list(set(product_ids))),
        ]).ids
        return [('id', 'in', ids)]

    # im regulaeren ablauf bei action_done stock.move hat das gestoert; danach kein quant fehler
    # @api.constrains("reserved_quantity", "quantity")
    # def _check_over_reservation(self):
        # digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        # for self in self:
            # if self.location_id.usage == 'internal':
                # if round(self.quantity, digits) < round(self.reserved_quantity, digits):
                    # breakpoint()
                    # raise ValidationError(_("Cannot reserve {} for {}. Available {}.").format(
                        # self.reserved_quantity,
                        # self.product_id.default_code,
                        # self.quantity,
                    # ))

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
        breakpoint()
        digits = dp.get_precision('Product Unit of Measure')(self.env.cr)[1]
        self._merge_quants()
        for self in self:
            if not self.exists():
                continue
            if self.product_id.type not in ['product']:
                continue
            if self.location_id.usage not in ['internal']:
                continue
            if self.calculated_reservations > self.quantity:
                self.env['stock.move.line'].with_context(test_queue_job_no_delay=True)._model_make_quick_inventory(
                    self.location_id,
                    0,
                    self.product_id,
                    self.lot_id,
                    add=self.calculated_reservations - self.quantity
                )
                self._merge_quants()
            if round(self.reserved_quantity, digits) != round(self.calculated_reservations, digits):
                self.sudo().reserved_quantity = self.calculated_reservations
        self._merge_quants()

    @api.model
    def _fix_all_reservations(self, commit=False):
        breakpoint()
        job_priority = int(self.env['ir.config_parameter'].get_param(key="fix_reservations.priority", default="2"))
        job_channel = self.env['ir.config_parameter'].get_param(key="fix_reservations.channel", default="fix_reservations")

        quants = self.search([('needs_fix_reservation', '=', True)], order='product_id, location_id')
        for i, quant in enumerate(quants.with_context(prefetch_fields=False)):
            quant = quant.browse(quant.id)
            if not quant.exists():
                continue
            print(f"SKU {quant.product_id.default_code}; {quant.id} {quant.product_id.default_code} {i} of {len(quants)}")
            if quant.calculated_reservations != quant.reserved_quantity:
                quant.with_delay(
                    channel=job_channel,
                    priority=job_priority,
                ).fix_reservation()
                if commit:
                    self.env.cr.commit()

    def _fix_missing_quant(self, lot, product, location_id, quantity):
        assert product
        assert isinstance(location_id, int)
        location = self.env['stock.location'].browse(location_id)
        inv = self.env['stock.inventory'].create({
            "location_id": location.id,
            "filter": "product",
            "company_id": self.env.user.company_id.id,
            "name": "Fix Quant Inventory {}: {} [{}]".format(location.name, lot.name, product.default_code),
            "product_id": product.id,
        })
        inv.action_start()
        inv.line_ids.unlink()
        inv.line_ids = [[0, 0, {
            'prod_lot_id': lot.id,
            'product_id': product.id,
            'location_id': location.id,
            'product_qty': quantity,
        }]]
        inv.action_done()

        # also still broken after that
        if lot.id:
            domain = [
                ('location_id.usage', '=', 'internal'),
                ('product_id', '=', product.id),
                ('location_id', '=', location_id),
            ]
            if lot:
                domain += [('lot_id', '=', lot.id)]
            self.env['stock.quant'].search(domain).fix_reservation()

        return inv
