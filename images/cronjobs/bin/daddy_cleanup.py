import os
import glob
import argparse
import pathlib
import logging
import time
import datetime as dt


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
            if is_dir and recursive:
                log.debug("Recursion not implemented yet")
            elif is_file:
                yield (path, mtime)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger()
    p = argparse.ArgumentParser("Gets the last file created this week, last week, second to last week, third to last week, last month, last quarter and last year by UTC time.")
    # p.add_argument("-l", default=False, help="Local time. Default is UTC.")
    p.add_argument("--recursive", help="Recurse into all subdirectories")
    p.add_argument("PATH", nargs="+", help="Paths or glob(s)")
    args = p.parse_args()
    log.debug(args.PATH)
    log.debug(args.recursive)
    now = dt.datetime.utcnow()
    now_time = time.gmtime()
    end_of_week = dt.datetime(year=now.year, month=now.month, day=now.day) + dt.timedelta(days=6 - now.weekday(), hours=24)
    end_of_last_week = end_of_week - dt.timedelta(weeks=1)
    end_of_2ndlast_week = end_of_week - dt.timedelta(weeks=2)
    end_of_3rdlast_week = end_of_week - dt.timedelta(weeks=3)
    end_of_4thlast_week = end_of_week - dt.timedelta(weeks=4)
    start_of_month = dt.datetime(year=now.year, month=now.month, day=1)
    end_of_last_month = start_of_month - dt.timedelta(days=1) # ah well it's late...
    start_of_last_month = dt.datetime(year=end_of_last_month.year,
            month=end_of_last_month.month,
            day=1)
    log.debug(f"Now: {now}")
    log.debug(f"end of week: {end_of_week}")
    log.debug(f"end of week: {end_of_last_week}")
    bins = {"this_week": (0, ''),
            "last_week": (0, ''),
            "2ndlast_week": (0, ''),
            "3rdlast_week": (0, ''),
            "last_month": (0, ''),
            "last_quarter": (0, ''),
            "last_year": (0, '')
            }
    for path, mt in genPathInfos(args.PATH):
        mt_dt = dt.datetime.utcfromtimestamp(mt)
        if mt_dt < end_of_week and (end_of_week - dt.timedelta(weeks=1)) < mt_dt:
            bins["this_week"] = max((mt, path), bins["this_week"])
        elif mt_dt < end_of_last_week and end_of_2ndlast_week < mt_dt:
            bins["last_week"] = max((mt, path), bins["last_week"])
        elif mt_dt < end_of_2ndlast_week and end_of_3rdlast_week < mt_dt:
            bins["2ndlast_week"] = max((mt, path), bins["2ndlast_week"])
        elif mt_dt < end_of_3rdlast_week and end_of_4thlast_week < mt_dt:
            bins["3rdlast_week"] = max((mt, path), bins["3rdlast_week"])
        if mt_dt < start_of_month and mt_dt < start_of_last_month:
            bins["last_month"] = max((mt, path), bins["last_month"])
        if mt_dt.year == now.year - 1:
            bins["last_year"] = max((mt, path), bins["last_year"])
        quarters = [(1, 3), (4, 6), (7, 9), (10, 12)]
        quarters.reverse()
        last_quarter = None
        for i, q in enumerate(quarters):
            if now.month >= q[0] and now.month <= q[1]:
                last_quarter = quarters[(i + 1) % 4]
                log.debug(f"Last quarter: {last_quarter}")

        if mt_dt.month >= last_quarter[0] and mt_dt.month <= last_quarter[1]:
            bins["last_quarter"] = max((mt, path), bins["last_quarter"])

    print(bins)
