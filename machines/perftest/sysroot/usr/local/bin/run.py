#!/usr/bin/python

import inspect
import os
import xmlrpclib
import time
import subprocess
import sys
import tests
import tinydb
import traceback
import logging
from datetime import datetime
from tinydb import TinyDB, where, Query

def getenv(name):
    result = os.getenv(name, "NOTSET")
    if result == "NOTSET":
        raise Exception("Missing env: {}".format(name))
    return result


host = "http://proxy"
username = "admin"
pwd = getenv("PASSWORD")
db = getenv("DBNAME")

duration_for_output = long(getenv("DURATION_TO_OUTPUT"))

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler
logger.setLevel(getenv("LOGLEVEL"))

def login(username, password):
    logger.debug("Logging in: %s", username)
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (host))
    uid = socket_obj.login(db, username, password)
    if not uid:
        raise Exception("Login failed for: %s" % username)
    return uid


while True:
    try:
        uid = login(getenv("USERNAME"), pwd)
        break
    except Exception:
        logger.warn("Login failed: either wrong username/password or odoo not available")
        time.sleep(5)

def exe(*params):
    global uid
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (host))
    return socket_obj.execute(db, uid, pwd, *params)


localdb = TinyDB("/opt/data.json")

while True:
    try:
        for name, d in tests.__dict__.iteritems():
            if callable(d):
                A = datetime.now()
                logger.debug("Executing {}".format(name))
                d(exe)
                B = datetime.now()
                duration = (B - A).total_seconds()
                if duration > duration_for_output:
                    logger.warn("Duration: %s for %s", duration, name)
                localdb.insert({'duration': duration, 'name': name, 'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

                q = Query()
                records = localdb.search(q.name == name)
                avg = sum(x['duration'] for x in records) / len(records)
                m = max(x['duration'] for x in records)
                logger.info("%s: %ss (avg), max: %ss", name, avg, m)
        time.sleep(long(getenv("SLEEP")))
    except Exception:
        msg = traceback.format_exc()
        logger.error(msg)
        time.sleep(long(getenv("SLEEP")))
