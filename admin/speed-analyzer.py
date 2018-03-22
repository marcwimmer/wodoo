import inspect
from datetime import datetime
import os
import xmlrpclib
import time
import subprocess
import sys

host = "http://localhost:8069"
username = "mw"
pwd = "1"
db = "cpb"

MODEL = 'sale.order'
FIELDS = ["message_needaction","type_id","tag_ids","name","date_order","partner_id","user_id","amount_total","to_invoice_amount","open_amount","paid_amount","currency_id","invoice_status","state","date_services_done","delivery_state","age_in_days"]
REPEAT = 3


def login(username, password):
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/common' % (host))
    uid = socket_obj.login(db, username, password)
    return uid
uid = login(username, pwd)

def exe(*params):
    global uid
    socket_obj = xmlrpclib.ServerProxy('%s/xmlrpc/object' % (host))
    return socket_obj.execute(db, uid, pwd, *params)


measures = {}

for f in FIELDS:
    print "measuring {}".format(f)
    measures.setdefault(f, [])

    for i in range(REPEAT):
        started = datetime.now()
        exe(MODEL, 'search_read', [], [f])
        duration = datetime.now() - started
        measures[f].append(duration.total_seconds())

ranking = []
for k in measures:
    avg = float(sum(measures[f]) // float(len(measures[f])))
    ranking.append((avg, k))
ranking = sorted(ranking, key=lambda r: r[0])
for i, r in enumerate(ranking):
    print "{}: {}s {}".format(i + 1, round(r[0], 1), r[1])
