FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get -y upgrade && apt-get install -y openvpn  ntp ntpdate net-tools && mkdir /root/transfer /root/ovpn /root/tools
ADD ./scripts/* /root/tools/
RUN chmod a+x /root/tools/*.sh
CMD ["/root/tools/run.sh"]
