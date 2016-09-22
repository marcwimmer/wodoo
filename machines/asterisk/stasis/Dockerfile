FROM ubuntu:16.04
RUN apt-get update && apt-get install -y python2.7 python-pip libpython2.7-dev git vim cmake sox
# for marcvim 
RUN apt-get update && apt-get install -y ctags nodejs npm automake pkg-config libpcre3-dev zlib1g-dev liblzma-dev inotify-tools nginx iputils-ping net-tools
RUN pip install --upgrade pip 
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r  /tmp/requirements.txt
RUN apt-get install -y htop
RUN npm update -g

ADD nginx-config /etc/nginx/sites-available/default

# set root password
RUN echo "root:odoo"|chpasswd 

WORKDIR /
ADD run.sh run.sh
RUN chmod a+x run.sh

WORKDIR /root
RUN mkdir -p .ssh

WORKDIR /root/.ssh
ADD id_rsa id_rsa
ADD ssh_config_repo config
RUN chmod 600 id_rsa

# install vim environment
RUN git config --system http.postBuffer 1048576000

#defined in consts.py in ari connector
VOLUME /opt
RUN mkdir -p /install

WORKDIR /root
RUN echo "export TERM=xterm" >> .bashrc

CMD ["/run.sh"]
