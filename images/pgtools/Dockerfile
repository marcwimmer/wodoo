FROM ubuntu:20.04
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-12 python-dev build-essential git python3-pip procps sockstat

RUN pip3 install psycopg2 psutil setuptools
RUN git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python3 setup.py install --with-man

ENV PGCLIRC /var/lib/postgresql/.pgcli.config
RUN pip3 install pip --upgrade
RUN pip3 install pgcli pendulum tabulate
ADD pgcli.config "$PGCLIRC"
ADD keyring.config /var/lib/postgresql/.local/share/python_keyring/keyringrc.cfg
RUN chown postgres:postgres /var/lib/postgresql/.local/share/python_keyring/keyringrc.cfg && \
    chown -R postgres:postgres "$PGCLIRC"

CMD exit 0