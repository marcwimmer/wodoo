#!/usr/bin/python3

import datetime
import threading
import subprocess
import time
import os
import logging

INPUT = os.getenv("INPUT")
OUTPUT = os.getenv("OUTPUT")
FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

logger.info("Starting libreoffice converter daemon")

def setup_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)
    os.system("chown 1000:1000 '{}'".format(d))
    os.system("chmod a+rw '{}'".format(d))


setup_dir(INPUT)
setup_dir(OUTPUT)

while True:
    files = os.listdir(INPUT)
    for filename in files:
        filepath = os.path.join(INPUT, filename)

        try:
            subprocess.check_call([
                "/usr/bin/soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                OUTPUT,
                filepath
            ], timeout=10)
        except Exception:
            logger.error("Error converting File: {}".format(filename))
        finally:
            os.unlink(filepath)
        del filename
    time.sleep(1.0)
