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
            job_time = " ".join(job[:5])
            job_command = job[-1]
            yield (job_time, job_command)

def execute(job_cmd):
    logger.info("Executing: {}".format(job_cmd))
    os.system(job_cmd)


jobs = list(get_jobs())
next_dates = []

logging.info("Found jobs: {}".format(jobs))
while True:
    base = datetime.now()
    for job_time, job_cmd in jobs:
        print(croniter(job_time, base).get_next(datetime))
        if croniter(job_time, base).get_next(datetime) < base:
            execute(job_cmd)

    time.sleep(1)
