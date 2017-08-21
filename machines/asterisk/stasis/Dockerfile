FROM ubuntu:16.04
RUN apt-get update && apt-get install -y python2.7 python-pip libpython2.7-dev cmake sox htop nginx
ADD sysroot/ /

RUN \
pip install --upgrade pip && \
pip install -r /root/requirements.txt 

RUN \
echo "TERM=xterm" >> /etc/environment && \
chmod a+x /usr/local/bin/*.sh && \
chmod a+x /usr/local/bin/run

CMD ["/usr/local/bin/run"]
