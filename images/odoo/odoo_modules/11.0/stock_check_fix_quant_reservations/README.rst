=======================================
stock_check_fix_quant_reservations
=======================================

Happens without custom code in-between:

stock.move.line reserves items, where there is no stock.
stock.quant not updated accordingly.

What I observed is baes problem where stock.quant is updated.
If there is a serialize error, then update of quant fails.
Based on that further calculations are wrong.



Authors
------------

* Marc Wimmer <marc@itewimmer.de>

