#!/usr/bin/python
import time
import uuid
import traceback
import logging
import sys
import os
import cups
import uuid

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler

PATH=sys.argv[1]
if not PATH:
    raise Exception("Path require!")

while True:
    try:

        for dirpath, dirnames, filenames in os.walk(PATH):
            for filename in [f for f in filenames if f.endswith(".pdf")]:
                printer_queue = os.path.basename(dirpath)
                path = os.path.join(dirpath, filename)
                print printer_queue, path
                id = unicode(uuid).replace(u'-', u'')
                conn = cups.Connection()
                logger.info(u"Printing {}".format(path))
                conn.printFile(unicode(printer_queue), unicode(path), unicode(id), {})
                os.unlink(path)
    except:
        msg = traceback.format_exc()
        logger.error(msg)
    time.sleep(2)

