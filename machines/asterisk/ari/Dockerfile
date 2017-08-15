FROM ubuntu:16.04
RUN apt-get update && apt-get install -y python2.7 python-pip libpython2.7-dev iputils-ping net-tools ffmpeg netcat sox nginx vim
ADD sysroot/ /

RUN \
pip install --upgrade pip && \
pip install -r  /root/requirements.txt

RUN \
echo "cd /opt/odoo/active_customs/common/asterisk_ari" >> /root/.bashrc && \
echo "TERM=xterm" >> /etc/environment && \
chmod a+x /usr/local/bin/*.sh 

CMD ["/usr/local/bin/run.sh"]
