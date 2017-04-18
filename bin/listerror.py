#!/usr/bin/python

import subprocess
import sys
import re

pattern = re.compile("^[0-9]{4}\-[0-9]{2}\-[0-9]{2} ")


def ev():
    logoutput = subprocess.check_output(["docker logs --since " + sys.argv[2] + " " + sys.argv[1] + " 2>&1 | grep ERROR -A 50; exit 0"], stderr=subprocess.STDOUT, shell=True)
    loglines = logoutput.splitlines()
    pout = ''
    err = 0
    for line in loglines:
        if " ERROR " in line:
            pout += (line + '\n')
            err = 1
            continue
        elif err:
            if not re.search(pattern, line):
                pout += (line + '\n')
            else:
                err = 0
                pout += ("\n")
    print (pout)


if len(sys.argv) <> 3:
    print ("Parameters not set correctly! Please supply <name of container> and <time to evaluate> e.g. listerrors.py odoo 12h!")
else:
    ev()

