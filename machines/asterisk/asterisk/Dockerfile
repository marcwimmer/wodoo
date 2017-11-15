FROM ubuntu:16.04
ENV ASTERISK_VERSION=14.7.2
ENV DEBIAN_FRONTEND noninteractive
ARG ASTERISK_COUNTRY_ITU
RUN sed -i "s/# deb http/deb http/g" /etc/apt/sources.list \
&&  sed -i "s/# deb-src http/deb-src http/g" /etc/apt/sources.list \
&&  echo "APT::Install-Recommends "false";" > /etc/apt/apt.conf \
&&  echo "APT::Install-Suggests "false";" >> /etc/apt/apt.conf 

RUN apt update && \
	apt --yes autoremove && \
	apt install -y \
	build-essential \
	wget \
	libssl-dev \
	libncurses5-dev \
	libnewt-dev \
	libxml2-dev \
	libsqlite3-dev \
	uuid-dev \
	git \
	subversion \
	openssl \
	pkg-config \
	libjansson-dev \
	rsync && \
	apt clean all


RUN mkdir -p /tmp/install
WORKDIR /tmp/install
RUN wget "http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-$ASTERISK_VERSION.tar.gz" -O asterisk.tar.gz

RUN tar -zxvf asterisk.tar.gz
RUN mv asterisk-* asterisk
WORKDIR /tmp/install/asterisk
RUN git clone git://github.com/asterisk/pjproject pjproject
WORKDIR /tmp/install/asterisk/pjproject
RUN ./configure --prefix=/usr --enable-shared --disable-sound --disable-resample --disable-video --disable-opencore-amr CFLAGS='-O2 -DNDEBUG' && \
make dep && \
make && \
make install

WORKDIR /tmp/install/asterisk
RUN contrib/scripts/get_mp3_source.sh
RUN if [ -z "$ASTERISK_COUNTRY_ITU" ]; then echo "Please configure ASTERISK_COUNTRY_ITU."; exit 20; fi

RUN (echo 'yes'; echo "$ASTERISK_COUNTRY_ITU") | contrib/scripts/install_prereq install
RUN contrib/scripts/install_prereq install-unpackaged
RUN ./configure --with-crypto --with-srtp && \
make config && \
make menuselect && \
make NOISY_BUILD=yes && \
make install && \
make install-logrotate && \
make config && \
make samples

RUN apt install -y net-tools openvpn vim

ADD bin /opt/bin
RUN chmod a+x /opt/bin/*

CMD /opt/bin/run.sh

