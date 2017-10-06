# -*- coding: utf-8 -*-
import os
import git
import subprocess
from utils import get_branch
from utils import get_submodules
from utils import is_branch_merged
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class Branch(models.Model):
    _name = 'git.branch'

    @api.model
    def get_root_path(self):
        return os.path.join(os.environ["ODOO_HOME"], 'data', 'src', 'customs', os.environ['CUSTOMS'])

    name = fields.Char(string="Branch")
    merged_master = fields.Boolean("Merged Master")
    merged_deploy = fields.Boolean("Merged Deploy")

    @api.multi
    def merge_master(self):
        return self.merge('master')

    @api.multi
    def merge_deploy(self):
        return self.merge('deploy')

    @api.multi
    def merge(self, to_branch):
        return True

    @api.model
    def update_branches(self):
        path = self.get_root_path()
        repo = git.Repo(path)
        self.search([]).unlink()
        for branch in repo.branches:
            self.env['git.branch'].with_context(from_parse=True).create({
                'name': branch.name,
                'merged_master': is_branch_merged(path, branch, 'master'),
                'merged_deploy': is_branch_merged(path, branch, 'deploy'),
            })

        return {
            'view_type': 'form',
            'res_model': self._name,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
            'views': [
                (False, 'tree'),
                (False, 'form'),
            ],
        }
