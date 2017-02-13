FROM ubuntu:16.04
RUN apt-get update && apt-get install python python-pip -y && pip install pip --upgrade
RUN pip install tinydb
ADD sysroot/ /
ADD tests /root/tests
VOLUME /opt
CMD PYTHONPATH=/root /usr/local/bin/run.sh
