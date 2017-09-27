# -*- coding: utf-8 -*-
import os
import git
import subprocess
from utils import get_branch
from utils import get_submodules
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class MainModule(models.Model):
    _name = 'git.module'
    _order = 'sequence'

    name = fields.Char(string="Name")
    parent_id = fields.Many2one('git.module', string="Parent")
    branch_id = fields.Many2one('git.branch', string="Branch")
    branch_ids = fields.One2many('git.branch', 'module_id', string="Branches")
    main = fields.Boolean("Main App", default=False)
    module_ids = fields.One2many('git.module', 'parent_id', string="Sub-Modules")
    sequence = fields.Integer(default=10)

    @api.model
    def get_root_path(self):
        return os.path.join(os.environ["ODOO_HOME"], 'data', 'src', 'customs', os.environ['CUSTOMS'])

    @api.model
    def update_mods(self):
        main = self.create({
            'name': os.environ['CUSTOMS'],
            'main': True,
            'sequence': 1,
        })
        main.fetch_branches_and_submodules(self.get_root_path(), )

        return {
            'view_type': 'form',
            'res_model': self._name,
            'res_id': main.id,
            'view_id': False,
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
        }

    @api.one
    def fetch_branches_and_submodules(self, path):
        print path
        for submodule in get_submodules(path):
            odoo_submodule = self.env['git.module'].create({
                'name': submodule['name'],
                'parent_id': self.id,
            })
            odoo_submodule.fetch_branches_and_submodules(os.path.join(path, submodule['name']))

        repo = git.Repo(path)
        for branch in repo.branches:
            self.env['git.branch'].create({
                'name': branch.name,
                'module_id': self.id,
            })

        current_branch = get_branch(path)
        self.branch_id = self.branch_ids.filtered(lambda b: b.name == current_branch)

class Branch(models.Model):
    _name = 'git.branch'

    name = fields.Char(string="Branch")
    module_id = fields.Many2one('git.module', string="Module")
