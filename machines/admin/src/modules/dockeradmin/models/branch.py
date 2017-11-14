# -*- coding: utf-8 -*-
import os
import git
import subprocess
import logging
import traceback
from consts import ADMIN_BRANCHES_REGEX
from consts import DEPLOY_BRANCH
from consts import MASTER_BRANCH
from utils import get_branch
from utils import get_root_path
from utils import get_submodules
from utils import is_branch_merged
from utils import git_pull
from utils import merge
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError

logger = logging.getLogger(__name__)


class Branch(models.Model):
    _name = 'git.branch'

    name = fields.Char(string="Branch")
    merged_master = fields.Boolean("Merged Master")
    merged_deploy = fields.Boolean("Merged Deploy")
    sequence = fields.Char(compute="get_sequence")

    @api.one
    def get_sequence(self):
        zero = '000000000'
        if self.name in [DEPLOY_BRANCH, MASTER_BRANCH]:
            self.sequence = zero
        else:
            self.sequence = zero + (self.name or '').lower()

    @api.multi
    def merge_master(self):
        self.merge(MASTER_BRANCH)
        self.merged_master = True
        return True

    @api.multi
    def merge_deploy(self):
        self.merge(DEPLOY_BRANCH)
        self.merged_deploy = True
        return True

    @api.multi
    def merge(self, to_branch):
        self.ensure_one()
        try:
            merge(self.env.user.name, self.name, to_branch)
        except:
            msg = traceback.format_exc()
            logging.error(msg)
            raise UserError("Automatic merge failed - please contact software-developer for merging: \n\n{}".format(msg))
        return True

    @api.model
    def update_branches(self):
        path = get_root_path()
        repo = git.Repo(path)
        result = self.env['git.branch']
        for branch in repo.branches:
            branch_name = branch.name
            if ADMIN_BRANCHES_REGEX and not any(x.findall(branch_name) for x in ADMIN_BRANCHES_REGEX):
                continue

            result |= self.env['git.branch'].with_context(from_parse=True).create({
                'name': branch.name,
                'merged_master': is_branch_merged(branch, MASTER_BRANCH),
                'merged_deploy': is_branch_merged(branch, DEPLOY_BRANCH),
            })
        return result
