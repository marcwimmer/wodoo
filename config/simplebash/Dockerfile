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
	uuid-runtime 

RUN pip install pip --upgrade
ADD requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
ADD entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
ADD prepare_host_odoo_home.py /prepare_host_odoo_home.py
RUN chmod a+x /prepare_host_odoo_home.py
WORKDIR /opt/odoo
