FROM ubuntu:16.04
RUN apt-get update && apt-get install -y python-psycopg2 python-pip
RUN pip install pip --upgrade
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
