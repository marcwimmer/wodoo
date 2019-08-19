#!/usr/bin/python
from pathlib import Path
import time
import uuid
import traceback
import logging
import sys
import os
import cups
import shutil

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

assert sys.argv[1]
assert sys.argv[2]

PATH = Path(sys.argv[1])
PRINTED = Path(sys.argv[2])
if not PATH.exists():
    raise Exception("Path required!")
if not PRINTED.exists():
    raise Exception("Path Printed required!")

while True:
    try:

        for file in PATH.glob("**/*.pdf"):
            printer_queue = file.parent.name
            id = unicode(uuid.uuid4()).replace(u'-', u'')
            conn = cups.Connection()
            logger.info(u"Printing {} to queue: {}".format(file, printer_queue))
            try:
                conn.printFile(unicode(printer_queue), str(file), str(id), {})
                file.rename(PRINTED / file.name)
            except Exception as e:
                msg = traceback.format_exc()
                logger.error(msg)
    except Exception as e:
        msg = traceback.format_exc()
        logger.error(msg)
    time.sleep(2)
