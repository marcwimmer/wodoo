FROM postgres:9.5
RUN mkdir -p  /docker-entrypoint-initdb.d
ENV SNAPSHOT /opt/snapshot
RUN mkdir -p $SNAPSHOT

RUN apt-get update && apt-get install -y ssh rsync python2.7 sudo procps
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/g' /etc/ssh/sshd_config
RUN service ssh restart

RUN echo "root:postgres" | chpasswd
USER root
WORKDIR /root/
RUN mkdir -p .ssh
RUN chmod 700 .ssh
ADD authorized_keys .ssh/authorized_keys
RUN ls -lha /root/.ssh
WORKDIR /root/.ssh
RUN chmod 400 authorized_keys
RUN chown root authorized_keys

ADD backup.sh /backup.sh
ADD restore.sh /restore.sh
RUN chmod a+x /backup.sh /restore.sh

RUN ls -lha /root/

ADD entrypoint2.sh /entrypoint2.sh
RUN chmod a+x /entrypoint2.sh

VOLUME /opt/md5
RUN chmod a+w /opt/md5

ADD init.sql /docker-entrypoint-initdb.d/
USER root
CMD /entrypoint2.sh
