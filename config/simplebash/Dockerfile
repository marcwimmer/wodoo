FROM ubuntu:18.04
RUN apt update && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y \
	python \
	python-pip \
	gettext-base \
	python-psycopg2 \
	python-pip \
	pigz \
	shellcheck \
	sudo \ 
	postgresql-client-10 \
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
	iputils-ping

RUN pip install pip --upgrade
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# install docker cli
RUN curl https://download.docker.com/linux/static/stable/x86_64/docker-17.09.0-ce.tgz -o /tmp/docker.tgz
WORKDIR /opt
RUN tar xfz /tmp/docker.tgz
RUN rsync /opt/docker/ /usr/local/bin/ -arP
WORKDIR /

ADD pudb.cfg /root/.config/pudb/pudb.cfg

ADD entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
RUN \
git config --global user.email admin && \
git config --global user.name admin
WORKDIR /opt/odoo


# install postgres 10 client
#RUN add-apt-repository 'deb http://apt.postgresql.org/pub/repos/apt/ zesty-pgdg main'
#RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - ; \
#apt-get update
#RUN apt install postgresql-10
