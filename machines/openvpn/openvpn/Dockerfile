FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get -y upgrade && apt-get install -y openvpn && mkdir /root/transfer /root/ovpn /root/tools ntp ntpdate net-tools nmap
RUN apt-get install -y inetutils-ping net-tools
ADD ./scripts/* /root/tools/
RUN chmod a+x /root/tools/*.sh
WORKDIR /root
ADD scan_clients.sh scan_clients.sh
RUN chmod a+x *.sh
CMD ["/root/tools/run.sh"]
