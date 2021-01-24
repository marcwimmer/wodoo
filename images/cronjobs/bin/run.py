#!/usr/bin/python3
import arrow
import threading
import string
import os
import sys
import time
import logging
import subprocess
from croniter import croniter
from croniter import CroniterBadCronError
from datetime import datetime
FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

logger.info("Starting cronjobs")

def get_jobs():
    now = datetime.now()
    for key in os.environ.keys():
        if key.startswith("CRONJOB_"):
            job = os.environ[key]
            if not job:
                continue

            # either 5 or 6 columns; it supports seconds
            logger.info(job)
            schedule = job
            while schedule:
                try:
                    croniter(schedule, now)
                except Exception:
                    schedule = schedule[:-1]
                else:
                    break
            if not schedule:
                raise Exception(f"Invalid schedule: {job}")
            job_command = job[len(schedule):].strip()
            itr = croniter(schedule, now)
            yield {
                'name': key.replace("CRONJOB_", ""),
                'schedule': schedule,
                'cmd': job_command,
                'base': now,
                'next': itr.get_next(datetime),
            }

def replace_params(text):
    # replace params in there
    def _replace_params(text):
        text = string.Template(text).substitute(os.environ)
        text = text.format(
            customs=os.environ['CUSTOMS'],
            date=datetime.now(),
        )
        return text
    while True:
        text = _replace_params(text)
        if _replace_params(text) == text:
            break
    return text

def execute(job_cmd):
    logger.info(f"Executing: {job_cmd}")

    job_cmd = replace_params(job_cmd)
    os.system(job_cmd)

def run_job(job):
    i = 0
    try:
        while True:
            now = datetime.now()

            if i > 300:
                logging.info("Next run of %s at %s", job['cmd'], job['next'])
                i = 0

            if job['next'] < now:
                execute(job['cmd'])

                itr = croniter(job['schedule'], arrow.get().naive)
                job['next'] = itr.get_next(datetime)

            time.sleep(1)
            i += 1
    except Exception as ex:
        logger.error(ex)
        time.sleep(1)


if __name__ == "__main__":
    jobs = list(get_jobs())
    for job in jobs:
        logging.info(f"Job: {job['name']}")
    if len(sys.argv) > 1:
        job = [x for x in jobs if x['name'] == sys.argv[1]]
        if not job:
            logger.error(f"Job not found: {sys.argv[1]}")
            sys.exit(-1)
        cmd = job[0]['cmd']
        execute(cmd)
        sys.exit(0)

    next_dates = []

    for job in jobs:
        logging.info(f"Scheduling Job: {job}")
        logging.info(f"With replaced values in looks like: {replace_params(job['cmd'])}")
    displayed_infos = False

    logger.info("--------------------- JOBS ------------------------")
    for job in jobs:
        logger.info(replace_params(job['cmd']))

        t = threading.Thread(target=run_job, args=(job,))
        t.daemon = True
        t.start()

    while True:
        time.sleep(10000000)
