import re
import traceback
from datetime import datetime
from .tools import remove_webassets
from .tools import __replace_all_envs_in_str
from .tools import _execute_sql
from . import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import __hash_odoo_password

@cli.group(cls=AliasedGroup)
@pass_config
def turn_into_dev(config):
    pass

@turn_into_dev.command()
@pass_config
def turn_into_dev(config):
    if not config.devmode:
        raise Exception("""When applying this sql scripts, the database is not usable anymore for production environments.
Please set DEVMODE=1 to allow this""")
    __turn_into_devdb(config, config.get_odoo_conn())

def __collect_other_turndb2dev_sql():
    from .odoo_config import customs_dir
    dir = customs_dir() / 'devscripts'
    if not dir.exists():
        return ""
    sqls = []
    for file in dir.glob("turn-into-dev.sql"):
        sqls.append(file.read_text())
    return "\n\n".join(sqls)

def __turn_into_devdb(config, conn):
    from .odoo_config import current_version
    from .myconfigparser import MyConfigParser
    myconfig = MyConfigParser(config.files['settings'])
    env = dict(map(lambda k: (k, myconfig.get(k)), myconfig.keys()))

    # encrypt password
    env['DEFAULT_DEV_PASSWORD'] = __hash_odoo_password(env['DEFAULT_DEV_PASSWORD'])

    sql_file = config.dirs['images'] / 'odoo' / 'config' / str(current_version()) / 'turndb2dev.sql'
    sql = sql_file.read_text()

    sql += __collect_other_turndb2dev_sql() or ""

    sql = __replace_all_envs_in_str(sql, env)

    critical = False
    for line in sql.split("\n"):
        if not line:
            continue
        if line.startswith("--set critical"):
            critical = True
            continue
        elif line.startswith("--set not-critical"):
            critical = False
            continue

        comment = re.findall(r'\/\*[^\*^\/]*\*\/', line)
        if comment:

            def ignore_line(comment):
                comment = comment[2:-2]
                if 'if-table-exists' in comment:
                    table = comment.split("if-table-exists")[1].strip()
                    res = _execute_sql(
                        conn,
                        "select count(*) from information_schema.tables where table_schema='public' and table_name='{}'".format(table),
                        fetchone=True
                    )
                    return not res[0]
                return False

            if any(list(ignore_line(comment) for comment in comment[0].split(";"))):
                continue
        try:
            print(line)
            _execute_sql(conn, line)
        except Exception:
            if critical:
                raise
            msg = traceback.format_exc()
            print("failed un-critical sql:", msg)

    remove_webassets(conn)
