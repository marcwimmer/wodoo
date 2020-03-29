FROM debian:buster
ENV DOCKER_VERSION=docker-18.09.3
RUN apt update && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y python3-pip python3 curl rsync locales \
postgresql-client pv pigz

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=en_US.UTF-8
ENV LANG en_US.UTF-8 
ENV LC_ALL en_US.UTF-8

# install docker cli
RUN curl https://download.docker.com/linux/static/stable/x86_64/$DOCKER_VERSION.tgz -o /tmp/docker.tgz
WORKDIR /opt
RUN tar xfz /tmp/docker.tgz
RUN rsync /opt/docker/ /usr/local/bin/ -ar

WORKDIR /usr/local/bin
ADD requirements.txt /root/requirements.txt
RUN pip3 install -r /root/requirements.txt
ADD bin/ /usr/local/bin/
RUN apt install -y telnet
RUN chmod a+x /usr/local/bin/*.py
