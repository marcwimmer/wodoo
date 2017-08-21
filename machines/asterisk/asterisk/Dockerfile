FROM ubuntu:14.04
ARG ASTERISK_VERSION
# if in customizations is an asterisk directory, then enable asterisk, otherwise not
RUN apt-get update && apt-get install -y build-essential linux-headers-generic subversion git openvpn

RUN apt-get update && apt-get install -y build-essential linux-headers-generic libxml2-dev libncurses5-dev libreadline-dev libreadline6-dev libiksemel-dev libvorbis-dev libssl-dev libspeex-dev libspeexdsp-dev mpg123 libmpg123-0 sox openssl wget subversion openssh-server unzip python-pip

RUN git clone --depth 1 --branch 13.12.1 http://gerrit.asterisk.org/asterisk /tmp/asterisk
WORKDIR /tmp/asterisk
RUN echo "Adding MP3 support" && \
./contrib/scripts/get_mp3_source.sh && \
apt-get install -y build-essential wget aptitude gdb strace && \
./contrib/scripts/install_prereq install && \
./contrib/scripts/install_prereq install-unpackaged && \
./configure

ADD menuselect.makeopts menuselect.makeopts
RUN make -j8 && make install

ADD requirements.txt /root/requirements.txt
ADD bin/ /

RUN \
pip install pip --upgrade && \
pip install -r /root/requirements.txt && \
chmod a+x /*.sh

#  init jobs
RUN make config 

CMD ["/run.sh"]
