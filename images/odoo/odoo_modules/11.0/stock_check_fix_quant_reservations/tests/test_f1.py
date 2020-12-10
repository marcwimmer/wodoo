import arrow
import os
import pprint
import logging
import time
import uuid
from datetime import datetime, timedelta
from unittest import skipIf
from odoo import api
from odoo import fields
from odoo.addons.unit_test_complex import tests
from odoo.tests import common
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError, AccessError


class Tes(common.TransactionCase):

    def test_quants(self):
        self.env['stock.quant'].fix_quantity()
        pass
