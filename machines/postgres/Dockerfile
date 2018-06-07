FROM postgres:10.0
RUN mkdir -p  /docker-entrypoint-initdb.d

RUN apt-get update && apt-get install -y procps pigz sudo

ADD postgresql2.conf /opt/postgres.conf.d/postgresql2.conf
ADD init.sql /docker-entrypoint-initdb.d/
ADD entrypoint2.sh /entrypoint2.sh

RUN chmod a+x /backup.sh /restore.sh; \
mkdir -p /opt/postgres.conf.d; \
chown postgres:postgres /opt/postgres.conf.d; \
chown postgres:postgres /opt/postgres.conf.d -R; \
chmod a+x /entrypoint2.sh

CMD /entrypoint2.sh
