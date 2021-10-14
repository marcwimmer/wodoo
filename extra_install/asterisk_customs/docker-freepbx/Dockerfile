FROM tiredofit/nodejs:8-debian-latest
LABEL maintainer="Dave Conroy (dave at tiredofit dot ca)"

### Set Defaults
   ENV DB_EMBEDDED=TRUE \
       ENABLE_CRON=TRUE \
       ENABLE_SMTP=TRUE \
       ASTERISK_VERSION=13 \
       BCG729_VERSION=1.0.4 \
       UCP_FIRST=TRUE \
       ASTERISK_SERVER=freepbx-app \
       ASTERISK_ARI_USER=ariuser1 \
       ASTERISK_ARI_PASSWORD=password1 \
       ASTERISK_AMI_USER=an_ami_user2 \
       ASTERISK_AMI_PASSWORD=a_password

### install ssh access for connector;
    RUN apt update && apt install -y ssh;

### Install Dependencies
   RUN set -x ; \
       apt-get update ; \
       curl https://packages.sury.org/php/apt.gpg | apt-key add - ; \
       echo 'deb https://packages.sury.org/php/ stretch main' > /etc/apt/sources.list.d/deb.sury.org.list ; \
       apt-get update  ; \

### Install Development Dependencies
       ASTERISK_BUILD_DEPS=' \
            autoconf \
            automake \
            bison \
            build-essential \
            doxygen \
            flex \
            libasound2-dev \
            libcurl4-openssl-dev \
            libical-dev \
            libiksemel-dev \
            libjansson-dev \
            libmariadbclient-dev \
            libncurses5-dev \
            libneon27-dev \
            libnewt-dev \
            libogg-dev \
            libresample1-dev \
            libspandsp-dev \
            libsqlite3-dev \
            libsrtp0-dev \
            libssl-dev \
            libtiff-dev \
            libtool-bin \
            libvorbis-dev \
            libxml2-dev \
            linux-headers-amd64 \
            pkg-config \
            python-dev \
            subversion \
            unixodbc-dev \
            uuid-dev \
            ' \
            ; \
            \
### Install Runtime Dependencies
    apt-get install --no-install-recommends -y \
            $ASTERISK_BUILD_DEPS \
            apache2 \
            composer \
            fail2ban \
            flite \
            ffmpeg \
            git \
            g++ \
            iproute2 \
            iptables \
            lame \
            libiodbc2 \
            libicu-dev \
            libsrtp0 \
            mariadb-client \
            mariadb-server \
            mpg123 \
            net-tools \
            php5.6 \
            php5.6-cli \
            php5.6-curl \
            php5.6-gd \
            php5.6-ldap \
            php5.6-mbstring \
            php5.6-mysql \
            php5.6-sqlite \
            php5.6-xml \
            php5.6-zip \
            php-pear \
            procps \
            sox \
            sqlite3 \
            sudo \
            unixodbc \
            uuid \
            wget \
            whois \
            xmlstarlet \
            subversion \
            ; \
       \
### Install MySQL Connector
       cd /usr/src ; \
       curl -sSL  https://downloads.mariadb.com/Connectors/odbc/connector-odbc-2.0.15/mariadb-connector-odbc-2.0.15-ga-debian-x86_64.tar.gz | tar xvfz - -C /usr/src/ ; \
       cp mariadb-connector-*/lib/libmaodbc.so /usr/lib/x86_64-linux-gnu/odbc/ ; \
       \
### Add Users
       addgroup --gid 2600 asterisk ; \
       adduser --uid 2600 --gid 2600 --gecos "Asterisk User" --disabled-password asterisk ; \
       \
### Install Jansson
       git clone https://github.com/akheron/jansson.git /usr/src/jansson ; \
       cd /usr/src/jansson ; \
       autoreconf -i ; \
       ./configure ; \
       make ; \
       make install
       \
### Build Asterisk
RUN \
       cd /usr/src  && \
       curl -sSL http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-${ASTERISK_VERSION}-current.tar.gz | tar xvfz - -C /usr/src/ && \
       cd /usr/src/asterisk-${ASTERISK_VERSION}*/
RUN \
       cd /usr/src/asterisk-${ASTERISK_VERSION}*/ && \
       contrib/scripts/get_mp3_source.sh 
RUN \

       cd /usr/src/asterisk-${ASTERISK_VERSION}*/ && \
       contrib/scripts/get_mp3_source.sh ; \
       contrib/scripts/install_prereq install && \
       ./configure --with-resample --with-pjproject-bundled --with-ssl=ssl --with-srtp && \
       make menuselect/menuselect menuselect-tree menuselect.makeopts && \
       menuselect/menuselect --list-options
RUN \
       cd /usr/src/asterisk-${ASTERISK_VERSION}*/ && \
       menuselect/menuselect  --list-options

RUN \
       cd /usr/src/asterisk-${ASTERISK_VERSION}*/ && \
       menuselect/menuselect --disable BUILD_NATIVE \
                             --enable format_mp3 \
                             --enable app_fax \
                             --enable app_confbridge \
                             --enable app_originate \
                             --enable app_playback \
                             --enable app_chanspy \
                             --enable app_macro \
                             --enable app_record \
                             --enable app_record \
                             --enable app_senddtmf \
                             --enable app_softhangup \
                             --enable app_stasis \
                             --enable codec_opus \
                             --enable codec_silk \
                             --disable chan_sip \
                             --enable chan_pjsip \
                             --enable chan_console \
                             --enable chan_rtp \
                             --enable bridge_simple \
                             --enable bridge_softmix \
                             --enable bridge_holding \
                             --enable res_ari \
                             --enable res_ari_applications \
                             --enable res_ari_asterisk \
                             --enable res_ari_bridges \
                             --enable res_ari_channels \
                             --enable res_ari_device_states \
                             --enable res_ari_endpoints \
                             --enable res_ari_events \
                             --enable res_ari_mailboxes \
                             --enable res_ari_model \
                             --enable res_ari_playbacks \
                             --enable res_ari_recordings \
                             --enable res_ari_sounds \
                             --enable res_stasis \
                             --enable res_stasis_answer \
                             --enable res_stasis_device_state \
                             --enable res_stasis_mailbox \
                             --enable res_stasis_playback \
                             --enable res_stasis_recording \
                             --enable res_stasis_snoop \
                             --enable BETTER_BACKTRACES \
                             --disable MOH-OPSOUND-WAV \
                             --enable MOH-OPSOUND-GSM 
RUN \
       cd /usr/src/asterisk-${ASTERISK_VERSION}*/ && \
       make && \
       make install && \
       ldconfig
RUN \
#### Add G729 Codecs
       git clone https://github.com/BelledonneCommunications/bcg729 /usr/src/bcg729 ; \
       cd /usr/src/bcg729 ; \
       git checkout tags/$BCG729_VERSION ; \
       ./autogen.sh ; \
       ./configure --libdir=/lib ; \
       make ; \
       make install ; \
       \
       mkdir -p /usr/src/asterisk-g72x ; \
       curl https://bitbucket.org/arkadi/asterisk-g72x/get/default.tar.gz | tar xvfz - --strip 1 -C /usr/src/asterisk-g72x ; \
       cd /usr/src/asterisk-g72x ; \
       ./autogen.sh ; \
       ./configure --with-bcg729 --with-asterisk${ASTERISK_VERSION}0 --enable-penryn; \
       make ; \
       make install ; \
       \
### Cleanup 
       mkdir -p /var/run/fail2ban ; \
       cd / ; \
       rm -rf /usr/src/* /tmp/* ; \
       apt-get purge -y $ASTERISK_BUILD_DEPS ; \
       apt-get -y autoremove ; \
       apt-get clean ; \
       apt-get install -y make ; \
       rm -rf /var/lib/apt/lists/* ; \
       \
### FreePBX Hacks
       sed -i -e "s/memory_limit = 128M /memory_limit = 256M/g" /etc/php/5.6/apache2/php.ini ; \
       a2disconf other-vhosts-access-log.conf ; \
       a2enmod rewrite ; \
       a2enmod headers ; \
       rm -rf /var/log/* ; \
       mkdir -p /var/log/asterisk ; \
       mkdir -p /var/log/apache2 ; \
       mkdir -p /var/log/httpd ; \
       \
### Zabbix Setup
       echo '%zabbix ALL=(asterisk) NOPASSWD:/usr/sbin/asterisk' >> /etc/sudoers ; \
       \
### Setup for Data Persistence
       mkdir -p /assets/config/var/lib/ /assets/config/home/ ; \
       mv /home/asterisk /assets/config/home/ ; \
       ln -s /data/home/asterisk /home/asterisk ; \
       mv /var/lib/asterisk /assets/config/var/lib/ ; \
       ln -s /data/var/lib/asterisk /var/lib/asterisk ; \
       ln -s /data/usr/local/fop2 /usr/local/fop2 ; \
       mkdir -p /assets/config/var/run/ ; \
       mv /var/run/asterisk /assets/config/var/run/ ; \
       mv /var/lib/mysql /assets/config/var/lib/ ; \
       ln -s /data/var/run/asterisk /var/run/asterisk ; \
       rm -rf /var/spool/asterisk ; \
       ln -s /data/var/spool/asterisk /var/spool/asterisk ; \
       rm -rf /etc/asterisk ; \
       ln -s /data/etc/asterisk /etc/asterisk

### Networking Configuration
   EXPOSE 80 443 4445 4569 5060 5160 8001 8003 8008 8009 18000-20000/udp

### Files Add
ADD install /
RUN mkdir /data
RUN chmod a+rwx /data 
RUN chmod a+x /init.custom/* -R
RUN \
for file in $(ls /init.custom/*); \
    do \
    echo "";  \
    echo "";  \
    echo "--------------------------------------------------------------";  \
    echo " Executing $file "; \
    echo "--------------------------------------------------------------";  \
    echo "";  \
    echo "";  \
    eval "$file"; \
done
