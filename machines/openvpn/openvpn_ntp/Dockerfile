FROM ubuntu:16.04 
RUN apt-get update && apt-get install -y dnsutils ntp openvpn net-tools
ADD run.sh /run.sh
RUN chmod a+x /run.sh
CMD /run.sh
