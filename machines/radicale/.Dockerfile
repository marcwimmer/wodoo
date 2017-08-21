FROM ubuntu:16.04
RUN apt-get update && \
    apt-get install -y python git python-pip && \
    pip install pip --upgrade
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
ADD config.template /etc/radicale/config.template
ADD run.sh /run.sh
RUN chmod a+x /run.sh
CMD /run.sh
