import subprocess
import click
from datetime import datetime
from .tools import measure_time
from .tools import exec_file_in_path
from .cli import cli, pass_config, Commands
from .tools import _remove_postgres_connections, _execute_sql

def __get_snapshots(config):
    conn = config.get_odoo_conn().clone(dbname='postgres')
    snapshots = [x[0] for x in _execute_sql(
        conn,
        "select datname from pg_database where datname like '{}_%_snapshot_%'".format(
            config.dbname,
        ),
        notransaction=True,
        fetchall=True,
    )]
    return snapshots

def assert_environment(config):
    exec_file_in_path('createdb')
    exec_file_in_path('psql')
    exec_file_in_path('dropdb')

def restore(config, snap):
    _remove_postgres_connections(config.get_odoo_conn())
    subprocess.call([
        exec_file_in_path('dropdb'),
        config.dbname,
    ])
    subprocess.call([
        exec_file_in_path('createdb'),
        '-T',
        snap,
        config.dbname,
    ])

@measure_time
@click.pass_context
def make_snapshot(ctx, config, name):
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snapshot_name = f"{config.dbname}_{name}_snapshot_{now}"
    Commands.invoke(ctx, "backup", snapshot_name)
    return snapshot_name

def remove(config, snapshot):
    subprocess.call([
        exec_file_in_path('dropdb'),
        snapshot,
    ])
