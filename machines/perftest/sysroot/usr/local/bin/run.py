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


host = "http://odoo:8072"
username = "admin"
pwd = getenv("PASSWORD")
db = getenv("DBNAME")

duration_for_output = long(getenv("DURATION_TO_OUTPUT"))

FORMAT = '[%(levelname)s] %(name) -12s %(asctime)s %(message)s'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger('')  # root handler
logger.setLevel(logger.debug)

def login(username, password):
    logger.debug("Logging in: %s", username)
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (host))
    uid = socket_obj.login(db, username, password)
    if not uid:
        raise Exception("Login failed for: %s" % username)
    return uid


uid = login(getenv("USERNAME"), pwd)

def exe(*params):
    global uid
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (host))
    return socket_obj.execute(db, uid, pwd, *params)


db = TinyDB("/opt/data.json")

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
                db.insert({'duration': duration, 'name': name, 'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

                q = Query()
                records = db.search(q.name == name)
                avg = sum(x['avg'] for x in records) / len(records)
                logger.info("%s: %ss (avg)", name, duration)
        time.sleep(long(getenv("SLEEP")))
    except:
        msg = traceback.format_exc()
        logger.error(msg)
        time.sleep(long(getenv("SLEEP")))
