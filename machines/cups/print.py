#!/usr/bin/python
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

PATH = sys.argv[1]
PRINTED = sys.argv[2]
if not PATH:
    raise Exception("Path required!")
if not PRINTED:
    raise Exception("Path Printed required!")

while True:
    try:

        for dirpath, dirnames, filenames in os.walk(PATH):
            for filename in [f for f in filenames if f.endswith(".pdf")]:
                printer_queue = os.path.basename(dirpath)
                path = os.path.join(dirpath, filename)
                id = unicode(uuid).replace(u'-', u'')
                conn = cups.Connection()
                logger.info(u"Printing {} to queue: {}".format(path, printer_queue))
                try:
                    conn.printFile(unicode(printer_queue), unicode(path), unicode(id), {})
                    shutil.move(path, os.path.join(PRINTED, filename))
                except:
                    msg = traceback.format_exc()
                    logger.error(msg)
    except:
        msg = traceback.format_exc()
        logger.error(msg)
    time.sleep(2)
