#!/bin/bash
set -e
set -x

source /eval_odoo_settings.sh
/apply-env-to-config.sh
# Runs a migration script either SQL or PY

if [[ -z "$1" ]]; then
    echo "Please say 'before' or 'after'"
    exit 1
fi

beforeafter="$1"
cd "$ACTIVE_CUSTOMS"

if [[ ! -d "migration/$ODOO_VERSION" ]]; then
    exit 0
fi
cd "migration/$ODOO_VERSION"

if [[ -e "$beforeafter.sql" ]]; then
    sqlfile="$beforeafter.sql"
    python <<EOF
import os
import psycopg2
conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['DB_USER'], password=os.environ['DB_PWD'], host=os.environ['DB_HOST'], port=os.environ['DB_PORT'])
cr = conn.cursor()
try:
    print "Executing $sqlfile"
    with open("$sqlfile") as f:
        sql = f.read()
    cr.execute(sql)
    conn.commit()
except:
    conn.rollback()
    raise
finally:
    cr.close()
    conn.close()
EOF
fi

if [[ -e "$beforeafter.python" ]]; then
    pyfile="$beforeafter.sql"
    python <<EOF
import os
import psycopg2
conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['DB_USER'], password=os.environ['DB_PWD'], host=os.environ['DB_HOST'], port=os.environ['DB_PORT'])
cr = conn.cursor()
try:
    print "Executing $pyfile"
    import $pyfile
    $pyfile.run(cr)
    conn.commit()
except:
    conn.rollback()
    raise
finally:
    cr.close()
    conn.close()
EOF
    python -c "import $pyfile; $pyfile.run"
fi
