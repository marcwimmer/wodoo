FROM    ubuntu:20.04
ENV     DEBIAN_FRONTEND noninteractive
ENV     TERM xterm
ENV     ROUNDCUBE_VERSION=1.4.11
MAINTAINER Round Cube <rc@xxx.org>

WORKDIR /root
RUN mkdir -p /rc
RUN apt update
RUN apt -y upgrade
RUN apt search php.*7
RUN apt install -y php-net-ldap2 php-net-ldap3 php-imagick php7.4-common php7.4-gd php7.4-imap php7.4-json php7.4-curl php7.4-zip php7.4-xml php7.4-mbstring php7.4-bz2 php7.4-intl php7.4-gmp php7.4-fpm php7.4-sqlite3
RUN apt install -y nginx wget composer

RUN \
apt install -y python3-pip && \
pip3 install pip --upgrade && \
pip3 install wheel && \
pip3 install pathlib
RUN ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log

RUN rm -fr /usr/share/nginx/www && \
wget --no-check-certificate http://github.com/roundcube/roundcubemail/releases/download/$ROUNDCUBE_VERSION/roundcubemail-${ROUNDCUBE_VERSION}-complete.tar.gz -O - | tar xz && \
mv /root/roundcubemail-$ROUNDCUBE_VERSION /usr/share/nginx/www  && \
rm -Rf /usr/share/nginx/www/installer

WORKDIR /usr/share/nginx/www
RUN composer install --no-dev

ADD config.inc.php /usr/share/nginx/www/config/
ADD default /etc/nginx/sites-enabled/default
ADD launch.sh /root/
RUN nginx -c /etc/nginx/nginx.conf -t

COPY autologon.php /usr/share/nginx/www/plugins/autologon/autologon.php
CMD [ "bash", "/root/launch.sh" ]
