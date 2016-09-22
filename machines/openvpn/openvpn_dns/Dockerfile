FROM ubuntu:16.04 
RUN apt-get update && apt-get install -y dnsmasq dnsutils vim openvpn net-tools
ADD run.sh /root/run.sh
RUN chmod a+x /root/run.sh
ADD hosts.append /etc/hosts.append
ADD dnsmasq.conf /etc/dnsmasq.conf
CMD /root/run.sh
