FROM ubuntu:16.04
RUN apt-get update && apt-get install -y openvpn
RUN apt-get update && apt-get install -y dnsutils vim
RUN apt-get update && apt-get install -y iputils-ping net-tools
ADD run.sh /run.sh
RUN chmod a+x /run.sh
CMD /run.sh
