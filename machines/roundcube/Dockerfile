FROM    ubuntu:18.04
ENV     DEBIAN_FRONTEND noninteractive
ENV     TERM xterm
MAINTAINER Round Cube <rc@xxx.org>

RUN apt update && \
    apt -y upgrade && \
    apt install -y --no-install-recommends \
    nginx php-fpm nano wget sqlite3 procps \
    php-intl php-pear \
    php-net-smtp php-mail-mime \
    php-sqlite3
WORKDIR /root
# when roundcube grows older, change version in the download link, but also in the 'mv' command
RUN rm -fr /usr/share/nginx/www && \
wget --no-check-certificate http://github.com/roundcube/roundcubemail/releases/download/1.3.8/roundcubemail-1.3.8-complete.tar.gz -O - | tar xz
RUN ls -lhtra /root && \
mv /root/roundcubemail-1.3.8 /usr/share/nginx/www && \
pear install Mail_Mime Net_SMTP Net_Socket Net_IDNA2 Auth_SASL Net_Sieve Crypt_GPG  && \
pear install Auth_SASL Net_SMTP Net_IDNA2-0.1.1 Mail_mime Mail_mimeDecode && \
mkdir -p /rc

ADD config.inc.php /usr/share/nginx/www/config/
ADD default /etc/nginx/sites-enabled/default
ADD launch.sh /root/

CMD [ "bash", "/root/launch.sh" ]
