FROM ubuntu:20.04
ENV DOCKER_VERSION=docker-19.03.12
RUN apt update && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y python3-pip python3 curl rsync locales pv pigz telnet libpq-dev wget lsb-release

# install postgres 13
RUN apt -y install && \
export DEBIAN_FRONTEND=noninteractive && \
apt install -y postgresql postgresql-contrib 
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
apt update && \
apt -y install postgresql-14
# apt update && \
# apt install -y postgresql-13 postgresql-client-13

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
RUN chmod a+x /usr/local/bin/*.py
