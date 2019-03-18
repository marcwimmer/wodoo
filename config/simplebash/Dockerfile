FROM debian:buster
ENV DOCKER_VERSION=docker-18.09.3
RUN apt update && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y  \
	gettext-base \
	pigz \
	shellcheck \
	sudo \ 
	postgresql-client \
	uuid-runtime \
	git \
	rsync \ 
	curl \
	netcat \
	git-cola \
	tig \
	vim \
	gosu \
	net-tools \ 
	iputils-ping \
    pv \
    colordiff \
    silversearcher-ag \
    runc \
    python3-pip \
    locales \
    locales-all

ADD requirements.txt /requirements.txt
RUN pip3 install setuptools
RUN pip3 install -r /requirements.txt
RUN pip3 install buttervolume

# install docker cli
RUN curl https://download.docker.com/linux/static/stable/x86_64/$DOCKER_VERSION.tgz -o /tmp/docker.tgz
WORKDIR /opt
RUN tar xfz /tmp/docker.tgz
RUN rsync /opt/docker/ /usr/local/bin/ -arP
WORKDIR /

ADD pudb.cfg /root/.config/pudb/pudb.cfg
ADD docker.config /tmp/docker.config

RUN \
git config --global user.email admin && \
git config --global user.name admin

ADD odoo /usr/local/bin
RUN chmod a+x /usr/local/bin/odoo
RUN ln -s /usr/local/bin/odoo /usr/local/bin/o
RUN echo "PS1='${debian_chroot:+($debian_chroot)}\[\e[1;91m\][odoo]\[\e[0m\]:\w\$ '" >> /etc/bash.bashrc
RUN echo 'cd $LOCAL_ODOO_HOME' >> /etc/bash.bashrc

# make docker say something
RUN ln -sf /proc/1/fd/1 /docker_out

ADD entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

WORKDIR /opt/odoo
