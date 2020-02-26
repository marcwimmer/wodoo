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
                yield (path, mtime)


def get_last_quarter(now):
    quarters = [(1, 3), (4, 6), (7, 9), (10, 12)]
    quarters.reverse()
    last_quarter = None
    for i, q in enumerate(quarters):
        if now.month >= q[0] and now.month <= q[1]:
            last_quarter = quarters[(i + 1) % 4]
            log.debug(f"Last quarter: {last_quarter}")
            return last_quarter
    raise f"Quarter selection failed for current timestamp! {now}"


def get_start_of_week(ts, delta=0):
    '''Return the start of the week delta weeks removed frome the one ts is in.'''
    sow = dt.datetime(year=ts.year,
            month=ts.month,
            day=ts.day) - dt.timedelta(days=ts.weekday())
    return sow + dt.timedelta(weeks=delta)


def rm(path_list):
    log.info("Starting deletion:")
    for ts, path in path_list:
        path.unlink()
        log.info(f"Deleted: {path}")


def parse_args():
    p = argparse.ArgumentParser(
        """Gets the last file created this week, last week, second to last week,
        third to last week, last month, last quarter and last year by UTC time.""")
    p.add_argument("PATH", nargs="+", help="Paths or glob(s)")
    p.add_argument("--dry-run", action="store_true",
            help="Make no changes, just output information.")
    p.add_argument("--days", "-d",  metavar="D", action="store", type=int, default=14,
            help="Keep the last file of the last  N days. This is not relative to X")
    p.add_argument("--doNt-touch", "-n", metavar="N", action="store", type=int, default=1,
            help="Do not touch the last X days from today. Defaults to 1=yesterday")
    p.add_argument("--verbose", "-v", action="store_true",
            help="Produce verbose debug information.")
    return p.parse_args()


def select_to_bins(path_list, days_bins, days_notouch):
    now = dt.datetime.utcnow()
    start_of_last_week = get_start_of_week(now, -1)
    start_of_2ndlast_week = get_start_of_week(now, -2)
    start_of_3rdlast_week = get_start_of_week(now, -3)
    start_of_month = dt.datetime(year=now.year, month=now.month, day=1)
    end_of_last_month = start_of_month - dt.timedelta(days=2) # ah well it's late...
    start_of_last_month = dt.datetime(
            year=end_of_last_month.year,
            month=end_of_last_month.month,
            day=1)
    log.debug(f"Now: {now}")
    log.debug(f"start of last week: {start_of_last_week}")
    log.debug(f"last month: {start_of_last_month}-{start_of_month}")
    bins = collections.defaultdict(lambda: (0, ''))
    # bins = {
    #        "2ndlast_week": (0, ''),
    #        "3rdlast_week": (0, ''),
    #        "last_month": (0, ''),
    #        "last_quarter": (0, ''),
    #        "last_year": (0, '')
    #        }
    candidates = []
    for path, mt in genPathInfos(path_list):
        mt_dt = dt.datetime.utcfromtimestamp(mt)
        days_back = (now - mt_dt).days
        # Skip all younger than days to not be touched:
        if days_back < days_notouch:
            continue
        if days_back < days_bins:
            bins[str(days_back)] = max((mt, path), bins[str(days_back)])

        # select into bins who might be deletion candidates:
        if start_of_last_week > mt_dt >= start_of_2ndlast_week:
            bins["2ndlast_week"] = max((mt, path), bins["2ndlast_week"])
        elif start_of_2ndlast_week > mt_dt >= start_of_3rdlast_week:
            bins["3rdlast_week"] = max((mt, path), bins["3rdlast_week"])
        if start_of_month > mt_dt > start_of_last_month:
            bins["last_month"] = max((mt, path), bins["last_month"])
        if mt_dt.year == now.year - 1:
            bins["last_year"] = max((mt, path), bins["last_year"])
        last_quarter = get_last_quarter(now)
        if (now.year == mt_dt.year and (last_quarter[0] <= mt_dt.month <= last_quarter[1]) or (last_quarter == (10, 12) and now.year == mt_dt.year + 1)):
            bins["last_quarter"] = max((mt, path), bins["last_quarter"])
        candidates.append((mt, path))
    # remove all those from the candidates that ended up in bins:
    unbinned = [c for c in candidates if c not in bins.values()]
    return bins, unbinned

class PathJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pathlib.PosixPath):
            return str(obj)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger()
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)
    log.debug(args)
    bins, deletion_candidates = select_to_bins(
        args.PATH,
        args.days,
        args.doNt_touch
    )

    print(json.dumps({
        "keep": bins,
        "delete": deletion_candidates
    }, cls=PathJsonEncoder))

    if args.dry_run:
        print("Dry run! Taking no action!", file=sys.stderr)
        print("Would delete:")
        for x in deletion_candidates:
            print(x)
        exit(0)
    else:
        rm(deletion_candidates)
