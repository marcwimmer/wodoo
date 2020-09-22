FROM postgres:12
ENTRYPOINT ["/run.sh"]
CMD ["postgres"]
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-12 python-pip python-dev build-essential git python3-pip procps sockstat

RUN pip install psycopg2 psutil setuptools
RUN git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python setup.py install --with-man

ENV PGCLIRC /var/lib/postgresql/.pgcli.config
RUN pip3 install pgcli==3.0.0 tabulate
ADD pgcli.config "$PGCLIRC"
ADD keyring.config /var/lib/postgresql/.local/share/python_keyring/keyringrc.cfg
RUN chown postgres:postgres /var/lib/postgresql/.local/share/python_keyring/keyringrc.cfg && \
    chown -R postgres:postgres "$PGCLIRC"

ADD config* /
ADD run.sh /run.sh
COPY init/* /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d && \
    chmod a+x /docker-entrypoint-initdb.d/*.sh /run.sh
