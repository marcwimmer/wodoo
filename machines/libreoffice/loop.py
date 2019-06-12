#!/usr/bin/python

import time
import os
INPUT = os.getenv("INPUT")
OUTPUT = os.getenv("OUTPUT")

def setup_dir(d):
    os.makedirds(d)
    os.system("chown 1000:1000 '{}'".format(d))
    os.system("chmod a+rw '{}'".format(d))


setup_dir(INPUT)
setup_dir(OUTPUT)

while True:
    files = os.listdir(INPUT)
    for filename in files:
        filepath = os.path.join(INPUT, filename)
        del filename
        os.system("/usr/bin/soffice --headless --convert-to pdf --outdir '{}' '{}'".format(
            OUTPUT,
            filepath
        ))
        os.unlink(filepath)
    time.sleep(0.4)
