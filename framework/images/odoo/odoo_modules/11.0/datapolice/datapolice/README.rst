=========================
datapolice
=========================


<record model="data.police" id="products1">
  <field name="model">product.product</field>
  <field name="checkdef">check_incoming_noproduction_nopicking</field>
  <field name="name">Incoming stock moves, that have no production or picking-in</field>
</record>

@api.multi
def datapolice_check_same_lot_type(self):
    if self.origin_sales and self.matching_prod_product_ids:
        if not self.lot_type == self.matching_prod_product_ids:
            return False # can return also a string!
    elif (self.origin_buy or self.origin_buy) and self.matching_sales_product_ids:
        if not self.lot_type == self.matching_sales_product_ids:
            return False
    return True

or

<record model="data.police" id="products1">
  <field name="model">product.product</field>
  <field name="name">Incoming stock moves, that have no production or picking-in</field>
  <field name="expr">obj.name != 'not allowed'</field>
</record>


Contributors
------------

* Marc Wimmer <marc@itewimmer.de>

