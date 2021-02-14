FROM ubuntu:20.04
RUN apt update && \
    apt -y upgrade && \
    apt install -y --no-install-recommends \
    nginx  procps \
    python3-pip \
    python3 \
    python3-setuptools
RUN apt-get update && apt-get install -y python3.8 python3-pip
RUN pip3 install webssh
ADD nginx /etc/nginx/sites-enabled/default
RUN nginx -c /etc/nginx/nginx.conf -t
ADD launch.sh /root
RUN chmod a+x /root/launch.sh
EXPOSE 8080
CMD [ "bash", "/root/launch.sh" ]
