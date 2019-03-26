#!/usr/bin/python3
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
        if key.startswith("CRONJOB_BACKUP_"):
            job = os.environ[key]
            job = job.split(" ", 6)
            schedule = " ".join(job[:5])
            job_command = job[-1]
            yield {
                'schedule': schedule,
                'cmd': job_command,
                'base': datetime.now()
            }

def execute(job_cmd):
    logger.info("Executing: {}".format(job_cmd))
    os.system(job_cmd)


jobs = list(get_jobs())
next_dates = []

logging.info("Found jobs: {}".format(jobs))
while True:
    for job in jobs:
        next_run = croniter(job['schedule'], job['base']).get_next(datetime)
        logging.info("Next run of %s at %s", job['cmd'], next_run)
        if next_run < datetime.now():
            execute(job['cmd'])
            job['base'] = next_run

    time.sleep(1)
