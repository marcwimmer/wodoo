import os
from pathlib import Path
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from odoo.tools.safe_eval import safe_eval

class Uninstaller(models.AbstractModel):
    _name = 'server.tools.uninstaller'

    @api.model
    def uninstall(self):
        if not os.getenv("CUSTOMS_DIR", ""):
            raise Exception("Environment CUSTOMS_DIR required.")

        customs_dir = Path(os.environ['CUSTOMS_DIR'])
        manifest = safe_eval((customs_dir / 'MANIFEST').read_text())

        for mod in manifest.get("uninstall", []):
            mods = self.env['ir.module.module'].search([('name', '=', mod), ('state', 'in', ['to upgrade', 'to install', 'installed'])])
            if mods:
                mods.module_uninstall()
