#!/usr/bin/env python3
import os
from glob import glob
import arrow
from pathlib import Path
import calendar
import humanize
import argparse
import pathlib
import logging
import datetime as dt
import click
from . import cli, pass_config, Commands
from .tools import abort

DTF = "%Y-%m-%d %H:%M:%S"


log = logging.getLogger()


def _get_files_if_dir(path):
    for path in glob(str(path)):
        path = Path(path)
        if not path.name:
            continue
        if path.is_dir():
            for file in path.glob("*"):
                if file.is_file():
                    yield next(_get_files_if_dir(file))
        elif path.is_file():
            mtime = arrow.get(path.stat().st_mtime)
            is_dir = path.is_dir()
            is_file = path.is_file()
            log.debug(f"{path}: mtime {mtime} dir? {is_dir} file? {is_file}")
            yield (path, mtime)


def genPathInfos(arg_paths):

    for arg_path in arg_paths:
        po = pathlib.Path(arg_path)
        log.debug(po)
        yield from _get_files_if_dir(arg_path)


def rm(path_list, dry_run):
    now = arrow.utcnow()
    log.info("Starting deletion:")
    for path in path_list:
        if path.is_file():
            if dry_run:
                modified = arrow.get(path.stat().st_mtime)

                click.secho(
                    "dry run -- would delete:"
                    f"{modified.strftime(DTF)}"
                    f" {path} "
                    f" {humanize.naturaldelta(now - modified)}"
                )
            else:
                path.unlink()
                log.info(f"Deleted: {path}")


def get_bins():
    def _return(x, y):
        return _hour_0(x), _hour_235959(y)

    def _hour_0(d):
        return d.replace(hour=0, minute=0, second=0)

    def _hour_235959(d):
        return d.replace(hour=23, minute=59, second=59)

    winning_weekday = 6  # sunday
    start = arrow.get()
    while start.weekday() != winning_weekday:
        start = start.shift(days=-1)

    # last x weeks
    def get_weeks():
        X = start
        for i in range(4):
            yield _return(X.shift(days=-6), X)
            X = X.shift(weeks=-1)

    def get_months():
        X = start
        for i in range(6):
            X = X.shift(months=-1)
            last_of_month = calendar.monthrange(X.year, X.month)[1]
            yield _return(
                arrow.get(X.year, X.month, 1),
                arrow.get(X.year, X.month, last_of_month),
            )

    def get_quarters():
        X = start
        for i in range(12):
            X = X.shift(months=-1)
            if X.month not in (3, 6, 9, 12):
                continue
            last_of_month = calendar.monthrange(X.year, X.month)[1]
            yield _return(
                arrow.get(X.year, X.month, 1),
                arrow.get(X.year, X.month, last_of_month),
            )

    def get_years():
        for i in range(20):
            year_end = arrow.get().replace(year=arrow.get().year - i, month=12, day=31)
            yield _return(
                year_end.replace(day=1, month=1),
                year_end,
            )

    yield _return(start, start)
    yield from get_weeks()
    yield from get_months()
    yield from get_quarters()
    yield from get_years()


def get_to_delete_files(path_list, days_notouch):
    now = dt.datetime.utcnow()
    log.debug(f"Now: {now}")
    bins = {}
    for bin in set(get_bins()):
        bins.setdefault(bin, [])

    keep_safe = set()
    to_delete = []
    for path, mt in genPathInfos(path_list):
        if (arrow.utcnow() - mt).days <= days_notouch:
            print("Ignoring", path)
            keep_safe.add(path)
            continue

        for key in bins:
            if mt >= key[0] and mt <= key[1]:
                bins[key].append(path)
        else:
            to_delete.append(path)

    # sort arrays by date reverse; at position[0] is the file
    # that will survive
    for k in bins.keys():
        bins[k] = sorted(bins[k], key=lambda x: x.stat().st_mtime, reverse=True)

    # store pole positions in safe array
    [keep_safe.add(x[0]) for x in bins.values() if x]

    # collect all victims
    for files in bins.values():
        to_delete += files[1:]

    click.secho("==========================")
    click.secho("Kept:\n")
    size = print_files(sorted(keep_safe))
    click.secho(f"Keeping {humanize.naturalsize(size)}")
    click.secho("==========================")

    return list(set(to_delete) - keep_safe)


def print_files(files):
    size = 0
    for path in list(set(files)):
        size += path.stat().st_size
        date = arrow.get(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        click.secho(f"{path}: {date}")
    return size


@cli.command(
    help=(
        "Deletes file matching the given glob in PATH and keeps "
        "youngest files of last weeks, months, quarters and years. "
        "By providing --doNt-touch files can be provided, that are "
        "never touched. "
    )
)
@click.argument("path", required=True, nargs=-1)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Do not touch the last X days from today. Defaults to 1=yesterday",
)
@click.option(
    "-N",
    "--dont-touch",
    default=1,
    help="Do not touch the last X days from today. Defaults to 1=yesterday",
)
@pass_config
def daddy_cleanup(config, path, dry_run, dont_touch):
    if config.verbose:
        log.setLevel(logging.DEBUG)
    path = [Path(os.getcwd()) / x for x in path]
    deletion_candidates = list(sorted(set(get_to_delete_files(path, dont_touch))))
    if deletion_candidates:
        size = print_files(deletion_candidates)
        print("Going to delete ", humanize.naturalsize(size))
        rm(deletion_candidates, dry_run=dry_run)


@cli.command()
@click.argument("path", required=True, nargs=-1)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Do not touch the last X days from today. Defaults to 1=yesterday",
)
@click.option(
    "-N",
    "--dont-touch",
    default=1,
    help="Do not touch the last X days from today. Defaults to 1=yesterday",
)
@pass_config
def keep_last_file_of_day(config, path, dry_run, dont_touch):
    if config.verbose:
        log.setLevel(logging.DEBUG)
    files = []
    for path in path:
        for file, mtime in _get_files_if_dir(path):
            if (arrow.utcnow() - mtime).days <= dont_touch:
                continue
            files.append((file, mtime))
    if not files:
        abort("No files matching")
    size = 0
    files = sorted(files, key=lambda x: x[1], reverse=False)
    for file, mtime in files[:-1]:
        size += file.stat().st_size
        if dry_run:
            click.secho(f"Would delete: {file}", fg="yellow")
        else:
            file.unlink()
            click.secho(f"Deleted: {file}", fg="red")
    click.secho(f"Keeping: {files[-1][0]}", fg="green")
    click.secho(
        f"{'Theoretically' if dry_run else ''} Deleted size: {humanize.naturalsize(size)}"
    )
