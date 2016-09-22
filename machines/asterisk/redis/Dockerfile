FROM ubuntu:16.04
RUN apt-get update && apt-get install -y redis-server
ADD redis.conf /etc/redis/redis.conf
ADD flush.sh /flush.sh
RUN chmod a+x /flush.sh
CMD /usr/bin/redis-server
