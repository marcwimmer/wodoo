# -*- coding: utf-8 -*-
from utils import get_containers
from utils import restart_container
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError
class Container(models.Model):
    _name = 'docker.container'

    name = fields.Char("Name")
    status = fields.Char("Status")
    all_attrs = fields.Text("Attrs")
    public_port = fields.Text("Public Ports")

    @api.one
    def restart(self):
        restart_container(self.name)
        return True

    @api.model
    def update_docker(self):
        self.search([]).unlink()
        for container in get_containers():
            self.create({
                'name': u'; '.join(container['Names'].replace('/', '')),
                'status': container['Status'],
                'public_port': ', '.join([str(x['PublicPort']) for x in container.get('Ports') if x.get('PublicPort')]),
                'all_attrs': str(container),
            })

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
