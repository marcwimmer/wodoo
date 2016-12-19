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
                path = os.path.join(dirpath, filename)
                printer_queue = os.path.basename(path)
                id = unicode(uuid).replace(u'-', u'')
                conn = cups.Connection()
                logger.info(u"Printing {} to queue: {}".format(path, printer_queue))
                conn.printFile(unicode(printer_queue), unicode(path), unicode(id), {})
                os.unlink(path)
    except:
        msg = traceback.format_exc()
        logger.error(msg)
    time.sleep(2)

