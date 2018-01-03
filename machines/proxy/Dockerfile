FROM phusion/baseimage:0.9.22
ENV apache_version=2.4.29
ENV apr_version=1.6.3
ENV apr_util_version=1.6.1

RUN \
apt update

RUN apt install -y build-essential libpcre3-dev zlib1g-dev libexpat1-dev wget libnghttp2-dev libxml2-dev
WORKDIR /tmp
RUN wget -O apache.tar.gz http://www-eu.apache.org/dist//httpd/httpd-$apache_version.tar.gz
RUN wget -O apr.tar.gz http://www-eu.apache.org/dist//apr/apr-$apr_version.tar.gz
RUN wget -O apr-util.tar.gz http://www-eu.apache.org/dist//apr/apr-util-$apr_util_version.tar.gz
RUN tar xfz apache.tar.gz
RUN tar xfz apr.tar.gz
RUN tar xfz apr-util.tar.gz
WORKDIR /tmp/httpd-$apache_version

RUN mkdir -p srclib
RUN mv ../apr-$apr_version srclib/apr
RUN mv ../apr-util-$apr_util_version srclib/apr-util
RUN \
./configure \
--prefix=/usr/local/apache2 \
--enable-mods-shared=all \
--enable-deflate \
--enable-proxy \
--enable-proxy-balancer \
--enable-proxy-http \
--enable-proxy-hcheck \
--enable-proxy-http2 \
--enable-proxy-html \
--enable-proxy-headers \
--enable-lbmethod-byrequests \
--enable-heartbeat \
--enable-heartmonitor \
--enable-dav \
--enable-alias \
--enable-http2 \
--enable-xml2enc \
--enable-slotmem-shm \
--with-included-apr \
--with-mpm=prefork
RUN make -j 4
RUN make install

RUN sed -i 's|/usr/local/games|/usr/local/apache2/bin|g' /etc/environment 
RUN echo "Include /etc/proxy/*.host" >> /usr/local/apache2/conf/httpd.conf
RUN echo "Include conf/modules.enabled" >> /usr/local/apache2/conf/httpd.conf
RUN echo "Include conf/my.conf" >> /usr/local/apache2/conf/httpd.conf

COPY modules.enabled /usr/local/apache2/conf/modules.enabled
COPY my.conf /usr/local/apache2/conf/my.conf
COPY bin/service.sh /etc/service/apache/run
COPY bin/init.sh /etc/my_init.d/

RUN \
chmod a+x /etc/my_init.d/*.sh && \
chmod a+x /etc/service/apache/run && \
rm -Rf /tmp/*

WORKDIR /usr/local/apache2
