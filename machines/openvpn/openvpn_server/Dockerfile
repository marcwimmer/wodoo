FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get -y upgrade && apt-get install -y openvpn ntp ntpdate net-tools nmap inetutils-ping net-tools dnsutils nmap vim
ADD ./tools/* /root/tools/
RUN ls -lha /root/tools
RUN chmod a+x /root/tools/*.sh
WORKDIR /root
CMD ["/root/tools/run.sh"]
