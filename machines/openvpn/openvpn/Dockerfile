###
# DOCKER File to Create and manage openvpn
###
FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get upgrade -y && apt-get install -y openvpn easy-rsa python2.7 rsync python-pip
ADD web.py-0.38.tar.gz /root
RUN \
cd /root/web.py-0.38 && \
python setup.py install
ADD bin/* /usr/local/bin/
RUN \
chmod a+x /usr/local/bin/*.sh && \
chmod a+x /usr/local/bin/*.py
CMD echo "no entrypoint - good bye!"
