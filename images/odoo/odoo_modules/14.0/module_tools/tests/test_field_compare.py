#CHECKLIST

#
# 1. tabelle ir_module muss demo=true bei dem modul haben (mit contint sichergestellt)
# 2. import in tests muss direkt sein, ohne glob (sonst members nicht erkannt)
#
#
# -*- coding: utf-8 -*-
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
from odoo import models
from odoo.tests import common
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, RedirectWarning, ValidationError, AccessError

class DummyModel(models.Model):
    _name = 'unit_test.tools.fields_compare'

    char1 = fields.Char()
    int1 = fields.Integer()
    child_ids_o2m = fields.One2many('unit_test.tools.fields_compare.sub_model', 'parent_id')
    child_ids_m2m = fields.Many2many('unit_test.tools.fields_compare.sub_model', 'unit_test_fields_compare_rel', 'parent_id', 'child_id')

class DummyModelSub(models.Model):
    _name = 'unit_test.tools.fields_compare.sub_model'

    parent_id = fields.Many2one('unit_test.tools.fields_compare')
    char1 = fields.Char()
    int1 = fields.Integer()

class TestCase(common.TransactionCase):

    def setUp(self):
        super(TestCase, self).setUp()

    def test_case1(self):
        """   """
        values = {
            'char1': 'value1',
            'int1': 123,
            'child_ids_o2m': [
                [0, 0, {
                    'char1':  'o2m any value',
                }]
            ],
            'child_ids_m2m': [
                [0, 0, {
                    'char1':  'm2m any value',
                }]
            ]
        }
        dummy = self.env['unit_test.tools.fields_compare'].create(values)
        values.pop('child_ids_o2m')
        values.pop('child_ids_m2m')

        res = dummy.compare_dict(values)
        self.assertFalse(res, "Created with values dict, should be same value.")

        values = {
            'child_ids_o2m': [
                [0, 0, {
                    'char1':  'o2m any value',
                }]
            ],
        }
        res = dummy.compare_dict(values)
        self.assertFalse(not res, "Should now differ")

        child = dummy.child_ids_o2m
        child.parent_id = False
        self.assertFalse(child.compare_dict({
            'parent_id': False,
        }))
