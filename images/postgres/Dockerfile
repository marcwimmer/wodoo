FROM postgres:11
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-11 python-pip python-dev build-essential git
RUN pip install psycopg2 psutil setuptools
RUN git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python setup.py install --with-man
ADD config* /
ADD run.sh /run.sh
