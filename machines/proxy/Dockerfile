FROM phusion/baseimage:0.9.22

RUN \
apt update && \
apt install -y apache2

COPY apache2.conf /etc/apache2/conf-enabled/99-myconf.conf

COPY bin/service.sh /etc/service/apache/run
COPY bin/init.sh /etc/my_init.d/

RUN \
chmod a+x /etc/my_init.d/*.sh && \
chmod a+x /etc/service/apache/run
