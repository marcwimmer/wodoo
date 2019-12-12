FROM postgres:11
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN apt-get update && \
apt install -y postgresql-server-dev-* python-pip python-dev build-essential git && \
pip install psycopg2  && \
pip install psutil && \
pip install setuptools && \
git clone https://github.com/julmon/pg_activity.git  && \
cd pg_activity/ && \
python setup.py install --with-man
ADD config* /
ADD run.sh /run.sh
