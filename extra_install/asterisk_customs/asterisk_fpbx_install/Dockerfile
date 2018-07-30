FROM centos:7
# Freepbx 14 Asterisk 14
# following https://wiki.freepbx.org/display/FOP/Installing+FreePBX+14+on+CentOS+7

RUN \
yum -y update && \
yum -y groupinstall core base "Development Tools"
RUN \
adduser asterisk -m -c "Asterisk User"

#RUN \
#firewall-cmd --zone=public --add-port=80/tcp --permanent && \
#firewall-cmd --reload

RUN \
yum -y install lynx tftp-server unixODBC mysql-connector-odbc mariadb-server mariadb \
  httpd ncurses-devel sendmail sendmail-cf sox newt-devel libxml2-devel libtiff-devel \
  audiofile-devel gtk2-devel subversion kernel-devel git crontabs cronie \
  cronie-anacron wget vim uuid-devel sqlite-devel net-tools gnutls-devel python-devel texinfo \
  libuuid-devel

RUN \
rpm -Uvh https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
rpm -Uvh https://mirror.webtatic.com/yum/el7/webtatic-release.rpm

RUN \
yum remove php* && \
yum install -y php56w php56w-pdo php56w-mysql php56w-mbstring php56w-pear php56w-process php56w-xml php56w-opcache php56w-ldap php56w-intl php56w-soap

RUN \
curl -sL https://rpm.nodesource.com/setup_8.x | bash - && \
yum install -y nodejs

# Install Dependencies for Google Voice (if required)
RUN \
cd /usr/src && \
wget https://github.com/meduketto/iksemel/archive/master.zip -O iksemel-master.zip && \
unzip iksemel-master.zip && \
rm -f iksemel-master.zip && \
cd iksemel-master && \
./autogen.sh && \
./configure && \
make && \
make install

# Install and Configure Asterisk
RUN \
cd /usr/src && \
wget http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-14-current.tar.gz && \
wget -O jansson.tar.gz https://github.com/akheron/jansson/archive/v2.10.tar.gz

#Compile and Install jansson
RUN \
cd /usr/src && \
tar vxfz jansson.tar.gz && \
rm -f jansson.tar.gz && \
cd jansson-* && \
autoreconf -i && \
./configure --libdir=/usr/lib64 && \
make && \
make install

WORKDIR /usr/src
RUN tar xfz asterisk-14-current.tar.gz && rm asterisk-14-current.tar.gz
RUN ln -s asterisk-14* /usr/src/asterisk

WORKDIR /usr/src/asterisk
# Configure
RUN ./configure --libdir=/usr/lib64 --with-pjproject-bundled
RUN make menuselect.makeopts
RUN contrib/scripts/get_mp3_source.sh
RUN menuselect/menuselect \
  --disable BUILD_NATIVE \
  --enable cdr_csv \
  # --enable chan_sip \
  --enable res_snmp \
  --enable res_http_websocket \
  --enable res_hep_pjsip \
  --enable res_hep_rtcp \
  --enable res_sorcery_astdb \
  --enable res_sorcery_config \
  --enable res_sorcery_memory \
  --enable res_sorcery_memory_cache \
  --enable res_pjproject \
  --enable res_rtp_asterisk \
  --enable res_ari \
  --enable res_ari_applications \
  --enable res_ari_asterisk \
  --enable res_ari_bridges \
  --enable res_ari_channels \
  --enable res_ari_device_states \
  --enable res_ari_endpoints \
  --enable res_ari_events \
  --enable res_ari_mailboxes \                                                                                                                                                                                                    --enable res_ari_model \
  --enable res_ari_playbacks \
  --enable res_ari_recordings \
  --enable res_ari_sounds \
  --enable res_pjsip \
  --enable res_pjsip_acl \
  --enable res_pjsip_authenticator_digest \                                                                                                                                                                                       --enable res_pjsip_caller_id \
  --enable res_pjsip_config_wizard \
  --enable res_pjsip_dialog_info_body_generator \
  --enable res_pjsip_diversion \
  --enable res_pjsip_dlg_options \
  --enable res_pjsip_dtmf_info \
  --enable res_pjsip_empty_info \
  --enable res_pjsip_endpoint_identifier_anonymous \
  --enable res_pjsip_endpoint_identifier_ip \
  --enable res_pjsip_endpoint_identifier_user \
  --enable res_pjsip_exten_state \
  --enable res_pjsip_header_funcs \
  --enable res_pjsip_logger \
  --enable res_pjsip_messaging \
  --enable res_pjsip_mwi \
  --enable res_pjsip_mwi_body_generator \
  --enable res_pjsip_nat \
  --enable res_pjsip_notify \
  --enable res_pjsip_one_touch_record_info \
  --enable res_pjsip_outbound_authenticator_digest \
  --enable res_pjsip_outbound_publish \
  --enable res_pjsip_outbound_registration \
  --enable res_pjsip_path \
  --enable res_pjsip_pidf_body_generator \
  --enable res_pjsip_publish_asterisk \
  --enable res_pjsip_pubsub \
  --enable res_pjsip_refer \
  --enable res_pjsip_registrar \
  --enable res_pjsip_registrar_expire \
  --enable res_pjsip_rfc3326 \
  --enable res_pjsip_sdp_rtp \
  --enable res_pjsip_send_to_voicemail \
  --enable res_pjsip_session \
  --enable res_pjsip_sips_contact \                                                                                                                                                                                               --enable res_pjsip_t38 \                                                                                                                                                                                                        --enable res_pjsip_transport_management \                                                                                                                                                                                       --enable res_pjsip_transport_websocket \
  --enable res_pjsip_xpidf_body_generator \
  --enable res_stasis \
  --enable res_stasis_answer \
  --enable res_stasis_device_state \
  --enable res_stasis_mailbox \
  --enable res_stasis_playback \
  --enable res_stasis_recording \
  --enable res_stasis_snoop \
  --enable res_stasis_test \
  --enable res_statsd \
  --enable res_timing_timerfd \
  menuselect.makeopts

RUN make
RUN make install
RUN make samples

# Update max number of open files.
RUN sed -i -e 's/# MAXFILES=/MAXFILES=/' /usr/sbin/safe_asterisk

# This is weird huh? I'd shell into the container and get errors about en_US.UTF-8 file not found
# found @ https://github.com/CentOS/sig-cloud-instance-images/issues/71
RUN localedef -i en_US -f UTF-8 en_US.UTF-8



RUN \
make && \
make install && \
make config && \
ldconfig && \
chkconfig asterisk off

# Set Asterisk ownership permissions.
RUN \
chown asterisk. /var/run/asterisk && \
chown -R asterisk. /etc/asterisk && \
chown -R asterisk. /var/{lib,log,spool}/asterisk && \
chown -R asterisk. /usr/lib64/asterisk && \
chown -R asterisk. /var/www/

RUN \
cd /usr/src && \
wget http://mirror.freepbx.org/modules/packages/freepbx/freepbx-14.0-latest.tgz && \
tar xfz freepbx-14.0-latest.tgz && \
rm -f freepbx-14.0-latest.tgz && \
cd freepbx && \
./start_asterisk start && \
./install -n
