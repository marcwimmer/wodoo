FROM postgres:12
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-12 python-pip python-dev build-essential git python3-pip procps sockstat
RUN pip install psycopg2 psutil setuptools
RUN git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python setup.py install --with-man
RUN pip3 install pgcli==2.2.0
ADD keyring.config /root/.local/share/python_keyring/keyringrc.cfg
ADD keyring.config /home/postgres/.local/share/python_keyring/keyringrc.cfg
ADD config* /
ADD run.sh /run.sh
COPY init/* /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d
RUN chmod a+x /docker-entrypoint-initdb.d/*.sh
ENTRYPOINT ["/bin/bash", "/run.sh"]
COPY docker-entrypoint.sh /usr/local/bin/
