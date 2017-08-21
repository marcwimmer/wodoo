FROM ubuntu:14.04
# if in customizations is an asterisk directory, then enable asterisk, otherwise not
RUN apt-get update && apt-get install -y build-essential linux-headers-generic subversion git openvpn

WORKDIR /root
RUN mkdir -p .ssh

WORKDIR /root/.ssh
ADD id_rsa id_rsa
ADD ssh_config_repo config
RUN chmod 600 id_rsa

RUN apt-get update && apt-get install -y build-essential linux-headers-generic libxml2-dev libncurses5-dev libreadline-dev libreadline6-dev libiksemel-dev libvorbis-dev libssl-dev libspeex-dev libspeexdsp-dev mpg123 libmpg123-0 sox openssl wget subversion openssh-server unzip

WORKDIR /tmp
#ENV ASTERISK_VERSION=13.2.1
ENV ASTERISK_VERSION=13.12.1
RUN git clone --depth 1 --branch 13.12.1 http://gerrit.asterisk.org/asterisk
WORKDIR /tmp/asterisk
RUN echo "Adding MP3 support"
RUN ./contrib/scripts/get_mp3_source.sh
RUN ls -lha ./contrib/scripts 
RUN apt-get install -y build-essential wget aptitude gdb strace
RUN ./contrib/scripts/install_prereq install
RUN ./contrib/scripts/install_prereq install-unpackaged
RUN ./configure
ADD menuselect.makeopts menuselect.makeopts


RUN make -j8
RUN make install
#
ADD requirements.txt /root/requirements.txt
RUN apt-get install -y python-pip
RUN pip install pip --upgrade
RUN pip install -r /root/requirements.txt

ADD reloader.sh /root/reloader.sh
RUN chmod a+x /root/reloader.sh
#
#  init jobs
RUN make config 
ADD run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
