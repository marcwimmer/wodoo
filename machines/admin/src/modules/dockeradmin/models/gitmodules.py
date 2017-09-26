# -*- coding: utf-8 -*-
import os
import git
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class MainModule(models.Model):
    _name = 'git.module'

    name = fields.Char(string="Name")
    parent_id = fields.Many2one('git.module', string="Parent")
    branch_id = fields.Many2one('git.branch', string="Branch")
    branch_ids = fields.One2many('git.branch', 'module_id', string="Branches")
    main = fields.Boolean("Main App", default=False)
    module_ids = fields.One2many('git.module', 'parent_id', string="Sub-Modules")

    @api.model
    def update_mods(self):
        repo = git.Repo(os.path.join(os.environ["ODOO_HOME"], 'data', 'src', 'customs', os.environ['CUSTOMS']))

        main = self.create({
            'name': os.environ['CUSTOMS'],
            'main': True,
        })
        main.fetch_branches_and_submodules(repo)

        return {
            'view_type': 'form',
            'res_model': self._name,
            'res_id': main.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
        }

    @api.one
    def fetch_branches_and_submodules(self, repo):
        for submodule in repo.submodules:
            odoo_submodule = self.env['git.module'].create({
                'name': submodule.name,
                'parent_id': self.id
            })
            odoo_submodule.fetch_branches_and_submodules()

        for branch in repo.branches:
            self.env['git.branch'].create({
                'name': branch.name,
                'module_id': self.id,
            })

class Branch(models.Model):
    _name = 'git.branch'

    name = fields.Char(string="Branch")
    module_id = fields.Many2one('git.module', string="Module")
