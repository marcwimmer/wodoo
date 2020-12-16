from odoo.tests import common
from datetime import datetime, timedelta
from odoo import fields, SUPERUSER_ID
import uuid
from odoo.addons.queue_job.job import FAILED, DONE


class TestClearQueueJobs(common.TransactionCase):
    _start_datetime = (datetime.now() - timedelta(days=365 * 100))

    def create_vals(self, vals):
        vals.update({
            'uuid': uuid.uuid1(),
            'user_id': SUPERUSER_ID,
            'date_created': fields.Datetime.to_string(self._start_datetime),
        })
        return vals

    def get_domain(self, state):
        return [
            ('state', '=', state),
            ('date_created', '<=', fields.Datetime.to_string(self._start_datetime)),
        ]

    def get_failed(self):
        return self.env['queue.job'].search(self.get_domain(FAILED))

    def get_done(self):
        return self.env['queue.job'].search(self.get_domain(DONE))

    def test_clear_queue_jobs(self):
        QUEUEJOB = self.env['queue.job']
        QUEUEJOB._log_access = False
        extra_days = 3
        days = QUEUEJOB._days_to_keep_done + extra_days
        _range = range(0, days)

        for days in _range:
            d = self._start_datetime
            if days:
                d = d - timedelta(days=days)
            vals = self.create_vals({
                'state': DONE,
                'date_done': fields.Datetime.to_string(d)
            })
            QUEUEJOB.create(vals)

        vals = self.create_vals({'state': DONE, 'date_done': False})
        QUEUEJOB.create(vals)

        vals = self.create_vals({'state': FAILED})
        QUEUEJOB.create(vals)

        expected_failed = 1
        expected_done = len(_range) + 1
        expected_done_after_clean = QUEUEJOB._days_to_keep_done + 1

        self.assertEqual(len(self.get_failed()), expected_failed)
        self.assertEqual(len(self.get_done()), expected_done)

        QUEUEJOB.clear_done_jobs(self._start_datetime)
        self.assertEqual(len(self.get_done()), expected_done_after_clean)
        self.assertEqual(len(self.get_failed()), expected_failed)
