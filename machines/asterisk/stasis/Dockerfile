FROM ubuntu:16.04
RUN apt-get update && apt-get install -y python2.7 python-pip libpython2.7-dev git vim cmake sox htop
ADD sysroot/ /

RUN \
pip install --upgrade pip && \
pip install -r  /root/requirements.txt && \
echo "TERM=xterm" >> /etc/environment && \
chmod a+x /usr/local/bin/*.sh && \
echo "You can call $(ls /usr/local/bin)" >> /root/.bashrc

CMD ["/usr/local/bin/run.sh"]
