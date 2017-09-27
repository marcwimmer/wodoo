# -*- coding: utf-8 -*-
import os
import time
from utils import get_containers
from utils import restart_container
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError
class Container(models.Model):
    _name = 'docker.container'
    _order = 'name'

    name = fields.Char("Name")
    status = fields.Char("Status")
    all_attrs = fields.Text("Attrs")
    public_port = fields.Text("Public Ports")

    @api.one
    def restart(self):
        restart_container(self.name)
        return self.refresh_action()

    @api.model
    def refresh_action(self):
        return {
            'view_type': 'form',
            'name': 'Running Containers Overview',
            'res_model': self._name,
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'options': {
            },
            'target': 'current',
        }

    @api.model
    def update_docker(self):
        self.search([]).unlink()

        minimum_containers = os.getenv("MINIMUM_CONTAINERS", "").split(',')

        for container in get_containers():
            odoo_container = self.create({
                'name': u'; '.join(container['Names']).replace('/', '').replace("{}_".format(os.environ['DCPREFIX']), ""),
                'status': container['Status'],
                'public_port': ', '.join([str(x['PublicPort']) for x in container.get('Ports') if x.get('PublicPort')]),
                'all_attrs': str(container),
            })
            if odoo_container.name in minimum_containers:
                minimum_containers.remove(odoo_container.name)

        # list most important containers, too
        for container in minimum_containers:
            odoo_container = self.create({
                'name': container,
                'status': "Down",
            })

        return self.refresh_action()
