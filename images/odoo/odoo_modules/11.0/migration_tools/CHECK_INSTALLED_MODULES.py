# prueft ob die module aus ir_module_module installiert sind und vorhanden sind; wenn nicht mehr im filesystem, dann werden sie geloescht-->vorher backupen!
import os
import psycopg2
print 'please enter dbname: default=cpb '
DB = raw_input() or "cpb"
conn = psycopg2.connect(host='postgres', user='odoo', password='odoo', database=DB)
cr = conn.cursor()

cr.execute("select id, name, state from ir_module_module")
for module in cr.fetchall():
    id, name, state = module
    paths = [
        "/opt/openerp/versions/server/addons/{}".format(name),
        "/opt/openerp/versions/server/openerp/addons/{}".format(name)
    ]

    if not any(os.path.isdir(x) for x in paths):
        print 'not found: ', name

        if state in ['installed', 'to upgrade', 'to install']:
            cr.execute("update ir_module_module set state = 'to uninstall' where id = %s", (id, ))

        if state in ['uninstalled']:
            cr.execute("delete from ir_module_module where id =%s", (id, ))

conn.commit()
cr.close()
conn.close()
