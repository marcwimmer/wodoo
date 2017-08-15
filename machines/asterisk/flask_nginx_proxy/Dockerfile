FROM ubuntu:16.04
RUN apt-get update && apt-get install -y nginx iputils-ping
ADD nginx.conf /etc/nginx/sites-available/
ADD run.sh /run.sh
RUN chmod a+x /run.sh
CMD /run.sh

