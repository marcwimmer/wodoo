FROM ubuntu:14.04
RUN apt-get update
RUN apt-get install -y python2.7 python-pip libpython2.7-dev git
RUN pip install --upgrade pip 
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r  /tmp/requirements.txt

WORKDIR /
ADD run.sh run.sh
RUN chmod a+x run.sh

WORKDIR /root
RUN mkdir -p .ssh

WORKDIR /root/.ssh
ADD id_rsa id_rsa
ADD ssh_config_repo config
RUN chmod 600 id_rsa


#defined in consts.py in ari connector
EXPOSE 29925 

CMD ["/run.sh"]
