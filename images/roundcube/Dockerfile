FROM    debian:stretch
ENV     DEBIAN_FRONTEND noninteractive
ENV     TERM xterm
ENV     ROUNDCUBE_VERSION=1.4.11
MAINTAINER Round Cube <rc@xxx.org>

RUN apt update && \
    apt -y upgrade && \
    apt install -y --no-install-recommends \
    nginx php-fpm nano wget sqlite3 procps \
    php-intl php-pear \
    php-net-smtp php-mail-mime \
    php-sqlite3 \
    php-mcrypt
WORKDIR /root
RUN ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log

# when roundcube grows older, change version in the download link, but also in the 'mv' command
RUN rm -fr /usr/share/nginx/www && \
wget --no-check-certificate http://github.com/roundcube/roundcubemail/releases/download/$ROUNDCUBE_VERSION/roundcubemail-${ROUNDCUBE_VERSION}-complete.tar.gz -O - | tar xz
RUN mv /root/roundcubemail-$ROUNDCUBE_VERSION /usr/share/nginx/www 

RUN mkdir -p /rc

ADD config.inc.php /usr/share/nginx/www/config/
ADD default /etc/nginx/sites-enabled/default
ADD launch.sh /root/

CMD [ "bash", "/root/launch.sh" ]
