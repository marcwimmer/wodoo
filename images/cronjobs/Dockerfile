FROM debian:buster
ENV DOCKER_VERSION=docker-18.09.3
RUN sed -i 's|http://deb.debian|http://ftp2.de.debian|g' /etc/apt/sources.list
RUN cat /etc/apt/sources.list
RUN apt update && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y python3-pip python3 curl rsync \
postgresql-client pv pigz

# install docker cli
RUN curl https://download.docker.com/linux/static/stable/x86_64/$DOCKER_VERSION.tgz -o /tmp/docker.tgz
WORKDIR /opt
RUN tar xfz /tmp/docker.tgz
RUN rsync /opt/docker/ /usr/local/bin/ -ar

WORKDIR /usr/local/bin
ADD requirements.txt /root/requirements.txt
RUN pip3 install -r /root/requirements.txt
ADD bin/ /usr/local/bin/
RUN chmod a+x /usr/local/bin/*.py
