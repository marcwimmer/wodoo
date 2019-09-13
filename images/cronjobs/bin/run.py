#!/usr/bin/python3
import string
import os
import sys
import time
import logging
import subprocess
from croniter import croniter
from datetime import datetime

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

logger.info("Starting cronjobs")

def get_jobs():
    for key in os.environ.keys():
        if key.startswith("CRONJOB_"):
            job = os.environ[key]
            job = job.split(" ", 6)
            schedule = " ".join(job[:5])
            job_command = job[-1]
            yield {
                'schedule': schedule,
                'cmd': job_command,
                'base': datetime.now()
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
    logger.info("Executing: {}".format(job_cmd))

    job_cmd = replace_params(job_cmd)
    os.system(job_cmd)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        execute(sys.argv[1])
        sys.exit(0)

    jobs = list(get_jobs())
    next_dates = []

    for job in jobs:
        logging.info("Scheduling Job: {}".format(job))
        logging.info("With replaced values in looks like: {}".format(replace_params(job['cmd'])))
    displayed_infos = False
    while True:
        for job in jobs:
            next_run = croniter(job['schedule'], job['base']).get_next(datetime)
            if not displayed_infos or (datetime.now().second == 0 and datetime.now().minute == 0):
                logging.info("Next run of %s at %s", job['cmd'], next_run)
            if next_run < datetime.now():
                execute(job['cmd'])
                job['base'] = next_run

        time.sleep(1)
        displayed_infos = True
