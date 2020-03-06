FROM postgres:11
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-11 python-pip python-dev build-essential git python3-pip
RUN pip install psycopg2 psutil setuptools
RUN git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python setup.py install --with-man
ADD config* /
ADD run.sh /run.sh
RUN pip3 install pgcli
ADD keyring.config /root/.local/share/python_keyring/keyringrc.cfg
ADD keyring.config /home/postgres/.local/share/python_keyring/keyringrc.cfg
