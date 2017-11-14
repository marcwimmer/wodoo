# -*- coding: utf-8 -*-
import os
import git
from utils import get_root_path
from utils import git_push
from utils import git_pull
from utils import git_fetch
from utils import git_state
from utils import git_checkout
from utils import get_branch
from utils import git_add
from utils import git_commit
from utils import switch_branch
from consts import MASTER_BRANCH
from consts import DEPLOY_BRANCH
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class VersionCommander(models.TransientModel):
    _name = 'version.commander'

    is_clean = fields.Boolean("Is Clean", compute="_get_state")
    name = fields.Char("Name", default="Version Commander")
    all_branch_ids = fields.Many2many('git.branch', string="Branches")
    unmerged_branch_ids = fields.Many2many('git.branch', string="Branches")
    git_state = fields.Text("State", compute="_get_state", store=False)
    action_ids = fields.One2many('commander.action', 'commander_id', string="Actions")

    @api.multi
    def start_commander(self):
        self = self.create({})
        return {
            'view_type': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'view_id': False,
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
                'initial_mode': 'view'
            }},
            'target': 'current',
        }

    @api.multi
    def update_branches(self):
        self.ensure_one()

        branches = self.env['git.branch'].update_branches()
        self.all_branch_ids = [[6, 0, branches.ids]]

        self.unmerged_branch_ids = [[6, 0, branches.filtered(lambda b: not b.merged_deploy).ids]]

    @api.multi
    def git_fetch(self):
        git_fetch()

    @api.multi
    def git_pull(self):
        git_pull()

    @api.multi
    def git_push(self):
        git_push()

    @api.one
    def _get_state(self):
        self.git_state = git_state()

        repo = git.Repo(get_root_path())

        if repo.untracked_files or [item.a_path for item in repo.index.diff(None)]:
            self.is_clean = False
        else:
            self.is_clean = True

    @api.multi
    def update_actions(self):
        self.action_ids.unlink()

        repo = git.Repo(get_root_path())

        for untracked_file in repo.untracked_files:
            self.env['commander.action'].create({
                'commander_id': self.id,
                'type': 'untracked_file',
                'argument': untracked_file,
            })
        for changed_file in [item.a_path for item in repo.index.diff(None)]:
            self.env['commander.action'].create({
                'commander_id': self.id,
                'type': 'modified',
                'argument': changed_file,
            })

    @api.multi
    def checkout_master(self):
        switch_branch(MASTER_BRANCH, force=True)
        self._get_state()
        return True

    @api.multi
    def checkout_deploy(self):
        switch_branch(DEPLOY_BRANCH, force=True)
        self._get_state()
        return True

class Actions(models.TransientModel):
    _name = 'commander.action'
    commander_id = fields.Many2one('version.commander', string='Commander')

    type = fields.Selection([('untracked_file', 'Untracked File'), ('modified', 'Modified File')])
    argument = fields.Char(size=512)
    done = fields.Boolean("Done")
    active = fields.Boolean(default=True)

    @api.multi
    def reload(self):
        return {
            'view_type': 'form',
            'res_model': 'version.commander',
            'res_id': self.commander_id.id,
            'view_id': False,
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'target': 'current',
        }

    @api.multi
    def do_restore(self):
        if self.type == 'modified':
            path = os.path.join(get_root_path(), self.argument)
            git_checkout(path)
            self.active = False
        else:
            pass
        return True

    @api.multi
    def do_delete(self):
        if self.type == 'untracked_file':
            path = os.path.join(get_root_path(), self.argument)
            os.unlink(path)
            self.active = False
        return self.reload()

    @api.multi
    def do_checkin(self):
        if get_branch() != 'deploy':
            raise ValidationError("Not on deploy branch - cannot commit.")
        if self.type in ['modified', 'untracked_file']:
            self.active = False
            if self.type == 'untracked_file':
                git_add(self.argument)
            git_commit(self.env.user.name, self.argument)

        return True
