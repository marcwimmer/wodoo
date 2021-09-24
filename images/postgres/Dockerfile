FROM postgres:12-bullseye
ENTRYPOINT ["/run.sh"]
CMD ["postgres"]
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-12 python-dev build-essential git python3-pip procps sockstat


ADD config* /
ADD run.sh /run.sh
COPY init/* /docker-entrypoint-initdb.d/
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d && \
    chmod a+x /docker-entrypoint-initdb.d/*.sh /run.sh
