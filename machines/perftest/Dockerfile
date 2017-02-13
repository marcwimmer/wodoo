FROM ubuntu:16.04
RUN apt-get update && apt-get install python python-pip -y && pip install pip --upgrade
RUN pip install tinydb pudb
ADD sysroot/ /
ADD tests.py /root/
VOLUME /opt
CMD PYTHONPATH=/root python /usr/local/bin/run.py
