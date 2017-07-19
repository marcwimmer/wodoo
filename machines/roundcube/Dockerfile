FROM    debian:jessie
ENV     DEBIAN_FRONTEND noninteractive
ENV     TERM xterm
MAINTAINER Round Cube <rc@xxx.org>

RUN apt-get -y update && apt-get -y upgrade && \
    apt-get install -y --no-install-recommends \
    nginx php5-fpm nano wget sqlite3 procps \
    php5-mcrypt php5-intl php5-sqlite php-pear \
    php-net-smtp php-mail-mime
WORKDIR /root
# when roundcube grows older, change version in the download link, but also in the 'mv' command
RUN rm -fr /usr/share/nginx/www && \
wget --no-check-certificate http://github.com/roundcube/roundcubemail/archive/release-1.2.tar.gz -O - | tar xz && \
mv /root/roundcubemail-release-1.2 /usr/share/nginx/www && \
pear install Mail_Mime Net_SMTP Net_Socket Net_IDNA2 Auth_SASL Net_Sieve Crypt_GPG  && \
pear install Auth_SASL Net_SMTP Net_IDNA2-0.1.1 Mail_mime Mail_mimeDecode && \
mkdir -p /rc

ADD config.inc.php /usr/share/nginx/www/config/
ADD default /etc/nginx/sites-enabled/default
ADD launch.sh /root/

CMD [ "bash", "/root/launch.sh" ]
