#!/usr/bin/env python3
# Runs a migration script either SQL or PY
import re
import subprocess
import os
import sys
import psycopg2
import importlib
from module_tools.odoo_config import customs_dir
from module_tools.odoo_config import get_version_from_customs
from pathlib import Path

if sys.argv[1] not in ['after', 'before']:
    raise Exception("Arg 1 must be before or after")

beforeafter = sys.argv[1]

migration_dir = customs_dir() / 'migration' / str(get_version_from_customs())
if not migration_dir.exists():
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
        # remove lines, beginning with comment
        sql = '\n'.join(filter(lambda line: not line.strip().startswith("--"), sql.split("\n")))
        for blockcomment in re.match(r'\/\*.*?\*\/', sql, re.DOTALL) or []:
            sql = sql.replace(blockcomment, "").strip()
        for statement in sql.split(";"):
            if not statement.strip():
                continue
            print("Executing {}".format(statement))
            cr.execute(statement)

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
