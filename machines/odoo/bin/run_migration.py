#!/usr/bin/env python
# Runs a migration script either SQL or PY
import subprocess
import os
import sys
import psycopg2
import importlib

subprocess.check_call([
    'bash',
    '-c',
    'source /eval_odoo_settings.sh; /apply-env-to-config.sh'
])

if sys.argv[1] not in ['after', 'before']:
    raise Exception("Arg 1 must be before or after")

beforeafter = sys.argv[1]

migration_dir = os.path.join(os.environ['ACTIVE_CUSTOMS'], 'migration', str(os.environ['ODOO_VERSION']))
if not os.path.isdir(migration_dir):
    sys.exit(0)
conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['DB_USER'], password=os.environ['DB_PWD'], host=os.environ['DB_HOST'], port=os.environ['DB_PORT'])
cr = conn.cursor()
try:

    sqlfile = os.path.join(migration_dir, beforeafter + '.sql')
    pyfile = os.path.join(migration_dir, beforeafter + '.py')
    if os.path.exists(sqlfile):
        print("Executing " + sqlfile)
        with open(sqlfile) as f:
            sql = f.read()
        cr.execute(sql)

    if os.path.exists(pyfile):
        print("Executing " + pyfile)
        sys.path.append(os.path.dirname(pyfile))
        importlib.import_module(beforeafter).run(cr)
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    cr.close()
    conn.close()
