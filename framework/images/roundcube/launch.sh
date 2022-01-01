#!/bin/bash
set -x
set -eux

sed -i "s/__MAIL_SERVER__/$MAIL_SERVER/g" /usr/share/nginx/www/config/config.inc.php && \

# make sure the dirs are there

mkdir -p /rc/logs
mkdir -p /rc/tmp
chown -R www-data:www-data /rc

phpenmod mcrypt
service nginx start
service php7.4-fpm start

tail -F /var/log/nginx/access.log &
tail -F /var/log/nginx/error.log
