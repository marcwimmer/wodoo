FROM ubuntu:16.04
RUN apt-get update && apt-get install python python-pip -y && pip install pip --upgrade
RUN pip install tinydb pudb
ADD sysroot/ /
ADD tests.py /usr/local/bin/
RUN chmod a+x /usr/local/bin/run.py
VOLUME /opt
CMD PYTHONPATH=/usr/local/bin python /usr/local/bin/run.py
