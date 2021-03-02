FROM    debian:stretch
ENV     DEBIAN_FRONTEND noninteractive
ENV     TERM xterm
ENV     ROUNDCUBE_VERSION=1.4.11
MAINTAINER Round Cube <rc@xxx.org>

WORKDIR /root
RUN mkdir -p /rc
RUN apt update && \
    apt -y upgrade && \
    apt install -y --no-install-recommends \
    nginx php-fpm nano wget sqlite3 procps \
    php-intl php-pear \
    php-net-smtp php-mail-mime \
    php-sqlite3 \
    php-mcrypt \
    python3-pip \
    python3 \
    python3-setuptools
RUN pip3 install pathlib
RUN ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log

RUN rm -fr /usr/share/nginx/www && \
wget --no-check-certificate http://github.com/roundcube/roundcubemail/releases/download/$ROUNDCUBE_VERSION/roundcubemail-${ROUNDCUBE_VERSION}-complete.tar.gz -O - | tar xz && \
mv /root/roundcubemail-$ROUNDCUBE_VERSION /usr/share/nginx/www  && \
rm -Rf /usr/share/nginx/www/installer

ADD config.inc.php /usr/share/nginx/www/config/
ADD default /etc/nginx/sites-enabled/default
ADD launch.sh /root/
RUN nginx -c /etc/nginx/nginx.conf -t

COPY autologon.php /usr/share/nginx/www/plugins/autologon/autologon.php
CMD [ "bash", "/root/launch.sh" ]
