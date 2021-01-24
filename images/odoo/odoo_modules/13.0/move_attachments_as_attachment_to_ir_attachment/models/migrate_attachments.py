import base64
from odoo.tools.sql import column_exists
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError, RedirectWarning, ValidationError

except_fields = ['favicon']

class MigrateAttachments(models.AbstractModel):
    _name = 'migrate.attachments'

    # env['migrate.attachments']._migrate_to_fs()
    @api.model
    def _migrate_to_fs(self):
        for field in self.env['ir.model.fields'].search([('ttype', '=', 'binary')]):
            print("-------------------")
            print(field.name)
            if field.name in ['x_studio_field_ncCIg', 'x_studio_field_z28Ux']: # x_studio_field_ncCIg_filename # TODO needfilanem for this
                continue
            obj = self.env[field.model_id.model]
            table = obj._name.replace('.', '_')
            if field.name not in obj._fields:
                print(f"TERMINATED does not exist: {field.name}")
                self.env.cr.execute(f"alter table {table} drop \"{field.name}\"")
                field.with_context(_force_unlink=True).unlink()
                continue
            objfield = obj._fields[field.name]
            print(objfield)
            if objfield.attachment:
                if field.name in except_fields:
                    continue
                if not column_exists(self.env.cr, table, field.name):
                    continue
                while True:
                    self.env.cr.execute((
                        f"select id, \"{field.name}\" from {table} "
                        f"where not \"{field.name}\" is null"
                    ))
                    try:
                        rec = self.env.cr.fetchone()
                    except Exception:
                        return
                    if not rec:
                        break
                    res_id = rec[0]
                    datas = rec[1]
                    print(res_id)

                    # datas
                    self.env.cr.execute("select id from ir_attachment where res_field=%s and res_model=%s and res_id=%s", (
                        field.name, obj._name, res_id
                    ))
                    existing_record = self.env.cr.fetchone()
                    # datas = base64.encodestring(datas)

                    if existing_record:
                        from pudb import set_trace
                        set_trace()
                        raise NotImplementedError()
                    else:
                        filenamefield = [x for x in obj._fields if field.name in x and x != field.name and obj._fields[x].type == 'char']
                        if not filenamefield:
                            filenamefield = [x for x in obj._fields if field.name.replace("_doc", "_filename") in x and x != field.name and obj._fields[x].type == 'char']
                        if not filenamefield:
                            from pudb import set_trace
                            set_trace()
                        filenamefield = filenamefield[0]
                        self.env.cr.execute(f"select \"{filenamefield}\" from {table} where id =%s", (
                            res_id,
                        ))
                        filename = self.env.cr.fetchone()[0] or str("unknown")
                        self.env['ir.attachment'].create({
                            'res_model': obj._name,
                            'res_field': field.name,
                            'res_id': res_id,
                            'datas': datas,
                            'name': filename,
                        })
                        self.env.cr.execute(f"update {table} set \"{field.name}\" = null where id=%s", (res_id,))
                self.env.cr.execute(f"alter table {table} drop \"{field.name}\"")
