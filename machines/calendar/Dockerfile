FROM phusion/baseimage:0.9.22

RUN \
apt update && \
apt install -y postgresql-client libdbi-perl libconfig-yaml-perl libdbd-pg-perl netcat-openbsd python python-pip python-psycopg2 apache2 php7.0 libapache2-mod-php7.0 php7.0-mysql php7.0-curl php7.0-gd php7.0-intl php-pear php-imagick php7.0-imap php7.0-mcrypt php-memcache  php7.0-pspell php7.0-recode php7.0-sqlite3 php7.0-tidy php7.0-xmlrpc php7.0-xsl php7.0-mbstring php-gettext php7.0-pgsql
RUN pip install pip==9.0.3 --upgrade && \
pip install cherrypy

RUN apt install -y rsync

COPY config.php /etc/davical/config.php
COPY pgpass /root/.pgpass
COPY init_*.sh /etc/my_init.d/
COPY adminservice.py /etc/service/adminservice/run
COPY apache2.sh /etc/service/apache2/run
RUN rm /etc/apache2/sites-enabled/000-default.conf
COPY apache2.conf /etc/apache2/sites-enabled/000-default.conf
 
RUN \
chmod a+x /etc/my_init.d/*.sh && \
chmod a+x /etc/service/adminservice/run && \
chmod a+x /etc/service/apache2/run && \
chmod 600 /root/.pgpass

WORKDIR /var/www/html
