#!/usr/bin/env python3
"""

Keeps the last file of a day.


"""
import arrow
import calendar
import humanize
import sys
import glob
import argparse
import pathlib
import logging
import time
import json
import datetime as dt
import collections


log = logging.getLogger()

def genPathInfos(arg_paths, recursive=False):
    for arg_path in arg_paths:
        po = pathlib.Path(arg_path)
        log.debug(po)
        igps = glob.iglob(arg_path)
        for glob_path in igps:
            path = pathlib.Path(glob_path)
            mtime = path.stat().st_mtime
            is_dir = path.is_dir()
            is_file = path.is_file()
            log.debug(f"{path}: mtime {mtime} dir? {is_dir} file? {is_file} ")
            if is_file:
                yield (path, arrow.get(mtime))


def rm(path_list, dry_run):
    now = arrow.utcnow()
    log.info("Starting deletion:")
    for path in path_list:
        if path.is_file():
            if dry_run:
                modified = arrow.get(path.stat().st_mtime)
                print(
                    "dry run -- would delete:",
                    modified.strftime("%Y-%m-%d %H:%M:%S"),
                    path,
                    humanize.naturaldelta(now - modified)
                )
            else:
                path.unlink()
                log.info(f"Deleted: {path}")


def parse_args():
    p = argparse.ArgumentParser(
        """Deletes file matching the given glob in PATH and keeps
           youngest files of last weeks, months, quarters and years.

           By providing --doNt-touch files can be provided, that are
           never touched.
        """)
    p.add_argument("PATH", nargs="+", help="Paths or glob(s)")
    p.add_argument("--dry-run", action="store_true",
            help="Make no changes, just output information.")
    p.add_argument("--doNt-touch", "-n", metavar="N", action="store", type=int, default=1,
            help="Do not touch the last X days from today. Defaults to 1=yesterday")
    p.add_argument("--verbose", "-v", action="store_true",
            help="Produce verbose debug information.")
    return p.parse_args()


def get_to_delete_files(path_list, days_notouch):
    now = dt.datetime.utcnow()
    log.debug(f"Now: {now}")

    keep_safe = set()
    to_delete = []
    files_per_day = {}
    for path, mt in genPathInfos(path_list):
        if (arrow.utcnow() - mt).days <= days_notouch:
            print("Ignoring", path)
            keep_safe.add(path)
            continue

        mt = mt.strftime("%Y-%m-%d")
        files_per_day.setdefault(mt, [])
        files_per_day[mt].append((mt, path))

    log.info("Kept:")
    size = print_files(sorted(keep_safe))
    log.info("Keeping", humanize.naturalsize(size))

    def _collect():
        for k in files_per_day:
            files = files_per_day[k]
            files = sorted(files, key=lambda x: x[0], reverse=True)
            files = files[1:]
            yield from files

    to_delete = list(_collect())

    return list(set(to_delete) - keep_safe)

def print_files(files):
    size = 0
    for path in list(set(files)):
        size += path.stat().st_size
        print(path, arrow.get(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
    return size


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    log = logging.getLogger()
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)
    log.debug(args)
    deletion_candidates = list(sorted(set(get_to_delete_files(
        args.PATH,
        args.doNt_touch
    ))))
    if deletion_candidates:
        size = print_files(deletion_candidates)
        print("Going to delete ", humanize.naturalsize(size))
        rm(deletion_candidates, dry_run=args.dry_run)
