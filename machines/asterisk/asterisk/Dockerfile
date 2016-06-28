FROM ubuntu:14.04
# if in customizations is an asterisk directory, then enable asterisk, otherwise not
RUN apt-get update
RUN apt-get install -y build-essential
RUN apt-get install -y linux-headers-generic
RUN apt-get install -y subversion git

WORKDIR /root
RUN mkdir -p .ssh

WORKDIR /root/.ssh
ADD id_rsa id_rsa
ADD ssh_config_repo config
RUN chmod 600 id_rsa

RUN apt-get install -y build-essential
RUN apt-get install -y linux-headers-generic
RUN apt-get install -y subversion git
RUN apt-get install -y libxml2-dev # Required
RUN apt-get install -y libncurses5-dev libreadline-dev libreadline6-dev  # Termcap stuff
RUN apt-get install -y libiksemel-dev # For Google Talk support
RUN apt-get install -y libvorbis-dev  # For Ogg Vorbis format support
RUN apt-get install -y libssl-dev # Needed for SIP
RUN apt-get install -y libspeex-dev libspeexdsp-dev  # For speex codec
RUN apt-get install -y mpg123 libmpg123-0 sox openssl wget subversion openssh-server # Odds and ends

WORKDIR /tmp
ENV ASTERISK_VERSION=13.2.1
RUN git clone --depth 1 --branch ${ASTERISK_VERSION} http://gerrit.asterisk.org/asterisk
WORKDIR /tmp/asterisk
RUN echo "Adding MP3 support"
RUN ./contrib/scripts/get_mp3_source.sh
RUN ls -lha ./contrib/scripts 
RUN apt-get install -y build-essential wget aptitude gdb strace
RUN ./contrib/scripts/install_prereq install
RUN ./contrib/scripts/install_prereq install-unpackaged
RUN ./configure
ADD menuselect.makeopts menuselect.makeopts
RUN make -j4
RUN make install

#  init jobs
RUN make config 
ADD run.sh /run.sh
RUN chmod a+x /run.sh

# add base config
ADD ./etc/asterisk /opt/etc.base


VOLUME /opt

CMD ["/run.sh"]
