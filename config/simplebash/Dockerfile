FROM ubuntu:17.10
RUN apt update && apt install -y \
	python \
	python-pip \
	gettext-base \
	python-psycopg2 \
	python-pip \
	pigz \
	shellcheck \
	sudo \ 
	postgresql-client \
	uuid-runtime \
	git \
	rsync \ 
	curl \
	netcat

RUN pip install pip --upgrade
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
ADD entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
RUN \
git config --global user.email admin && \
git config --global user.name admin
WORKDIR /opt/odoo
