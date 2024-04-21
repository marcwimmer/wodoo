import arrow
import sys
import click
import inquirer
from .cli import cli, pass_config, Commands
from .lib_clickhelpers import AliasedGroup
from .tools import get_filesystem_of_folder


def _decide_snapshots_possible(config):
    if not config.use_docker:
        return False
    ttype = get_filesystem_of_folder("/var/lib/docker")
    if ttype in ["zfs", "btrfs"]:
        return ttype


def _setup_manager(config):
    ttype = _decide_snapshots_possible(config)
    if ttype == "zfs":
        from . import lib_db_snapshots_docker_zfs as snapshot_manager
    elif ttype == "btrfs":
        from . import lib_db_snapshots_docker_btrfs as snapshot_manager
    else:
        from . import lib_db_snapshots_plain_postgres as snapshot_manager
    config.__choose_snapshot = __choose_snapshot
    config.snapshot_manager = snapshot_manager


@cli.group(cls=AliasedGroup)
@pass_config
def snapshot(config):
    _setup_manager(config)


def __choose_snapshot(config, take=False):
    snapshots = list(config.snapshot_manager.__get_snapshots(config))
    snapshots_choices = [f"{x['name']} from {x['date']}" for x in snapshots]

    if take:
        return take

    answer = inquirer.prompt([inquirer.List("snapshot", "", choices=snapshots_choices)])
    if not answer:
        sys.exit(0)
    snapshot = answer["snapshot"]
    snapshot = snapshots[snapshots_choices.index(snapshot)]

    return snapshot["name"]


@snapshot.command(name="list")
@pass_config
def do_list(config):
    config.snapshot_manager.assert_environment(config)
    snapshots = list(config.snapshot_manager.__get_snapshots(config))
    from tabulate import tabulate

    rows = [(x["name"], x["date"], x["path"]) for x in snapshots]
    click.echo(tabulate(rows, ["Name", "Date", "Path"]))


@snapshot.command(name="save")
@click.argument("name", required=False)
@pass_config
@click.pass_context
def snapshot_make(ctx, config, name):

    config.snapshot_manager.assert_environment(config)
    if not name:
        name = arrow.get().strftime("%Y%m%d_%H%M%S")
        click.secho(f"Using {name} as snapshot name")

    # remove existing snaps
    snapshot = config.snapshot_manager.make_snapshot(ctx, config, name)
    click.secho("Made snapshot: {}".format(snapshot), fg="green")


@snapshot.command(name="restore")
@click.argument("name", required=False)
@pass_config
@click.pass_context
def snapshot_restore(ctx, config, name):
    config.snapshot_manager.assert_environment(config)
    if not name:
        name = __choose_snapshot(config, take=name)
    if not name:
        return
    config.snapshot_manager.restore(config, name)


@snapshot.command(name="remove")
@click.argument("name", required=False)
@pass_config
@click.pass_context
def snapshot_remove(ctx, config, name):
    config.snapshot_manager.assert_environment(config)

    snapshot = __choose_snapshot(config, take=name)
    if not snapshot:
        return
    config.snapshot_manager.remove(config, snapshot)


@snapshot.command(name="clear", help="Removes all snapshots")
@pass_config
@click.pass_context
def snapshot_clear_all(ctx, config):
    config.snapshot_manager.assert_environment(config)

    if hasattr(config.snapshot_manager, "clear_all"):
        config.snapshot_manager.clear_all(config)
    else:
        snapshots = config.snapshot_manager.__get_snapshots(config)
        if snapshots:
            for snap in snapshots:
                config.snapshot_manager.remove(config, snap)
    ctx.invoke(do_list)


@snapshot.command(
    name="purge-inactive-subvolumes",
    help=(
        "Compares subvolumes to docker volumes. If the "
        "volume is not used anymore, then its subvolumes are cleared."
    ),
)
@pass_config
@click.pass_context
def snapshot_purge_inactive_subvolumes(ctx, config):
    config.snapshot_manager.assert_environment(config)
    config.snapshot_manager.purge_inactive(config)


@snapshot.command()
@pass_config
@click.pass_context
def remove_postgres_volume(context, config):
    """
    Called when odoo down -v or odoo down --postgres-volume is called
    """
    _setup_manager(config)
    if not config.RUN_POSTGRES:
        return
    if _decide_snapshots_possible(config) != "zfs":
        return
    config.snapshot_manager.remove_volume(config)


Commands.register(remove_postgres_volume)
