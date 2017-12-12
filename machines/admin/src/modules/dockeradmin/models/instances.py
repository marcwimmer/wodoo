# -*- coding: utf-8 -*-
import os
import time
from utils import get_containers
from utils import restart_container
from utils import start_container
from utils import stop_container
from utils import compose
from utils import reload_nginx
from openerp import _, api, fields, models, SUPERUSER_ID
from openerp.exceptions import UserError, RedirectWarning, ValidationError


class Instance(models.Model):
    _name = 'docker.odoo.instance'

    name = fields.Char("Name")
    hostname = fields.Char("Hostname", help="shipping.yourcompany.com")
    state = fields.Selection([('running', 'Running'), ('stopped', 'Stopped')], string='State', compute="_get_state", store=False)
    technical_name = fields.Char(compute="_get_technical_name", help="Name of docker container for ./odoo up xxx")

    @api.constrains('hostname')
    def check_hostname(self):
        if self.hostname:
            if '/' in self.hostname:
                raise ValidationError("Hostname may not contain '/'")

    @api.one
    def _get_technical_name(self):
        self.technical_name = "odoo_{}".format(self.name)

    @api.one
    def _get_state(self):
        self.state = 'running'
        self.env['docker.container'].update_docker()
        containers = self.env['docker.container'].search([])
        self.state = 'running' if containers.search_count([('name', '=', self.technical_name)]) else 'stopped'

    @api.multi
    def start(self):
        self.ensure_one()
        compose()
        start_container(self.technical_name)
        reload_nginx()
        time.sleep(3)

    @api.multi
    def stop(self):
        self.ensure_one()
        stop_container(self.technical_name)
        time.sleep(3)
        self._get_state()

    @api.model
    def create(self, vals):
        result = super(Instance, self).create(vals)
        if self.env.context.get("INSTANCE_UPDATE", False):
            self.update_contents()
        return result

    @api.multi
    def write(self, vals):
        super(Instance, self).write(vals)

        if self.env.context.get("INSTANCE_UPDATE", False):
            self.update_contents()
        return True

    @api.multi
    def unlink(self):
        super(Instance, self).unlink()
        if self.env.context.get("INSTANCE_UPDATE", False):
            self.update_contents()
        return True

    @api.model
    def get_content(self):
        path = os.environ['INSTANCES_FILE']
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write("")

        with open(path, 'r') as f:
            contents = f.read()
        return contents or ''

    @api.model
    def set_content(self, content):
        if not content.endswith("\n"):
            content += '\n'
        path = os.environ['INSTANCES_FILE']
        with open(path, 'w') as f:
            f.write(content)
        return True

    @api.model
    def update_contents(self):
        content = []
        for rec in self.search([]):
            content.append("{} {}".format(
                rec.name.replace("\n", ""),
                rec.hostname.replace("\n", ""),
            ))
        self.set_content('\n'.join(content))
        return True

    @api.model
    def update_instances(self):
        self.search([]).unlink()

        instances = self.env['docker.odoo.instance']

        for line in self.get_content().split("\n"):
            if not line:
                continue
            name, hostname = line.split(" ")

            instances |= self.create({
                'name': name,
                'hostname': hostname
            })

        return {
            'name': "Instances of odoo containers",
            'view_type': 'form',
            'res_model': self._name,
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'flags': {'form': {
                'action_buttons': True,
            }},
            'options': {
            },
            'domain': [('id', 'in', instances.ids)],
            'target': 'current',
            'context': {
                'INSTANCE_UPDATE': True,
            }
        }
