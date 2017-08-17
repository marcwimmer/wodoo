FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get -y upgrade && apt-get install -y openvpn net-tools nmap inetutils-ping net-tools dnsutils nmap easy-rsa
ADD ./tools/* /root/tools/
RUN \
mkdir -p /root/openvpn-ca && \
ln -s /etc/ssl/openssl.cnf /root/openvpn-ca/openssl-1.0.0.cnf && \
chmod a+x /root/tools/*.sh && \
perl -p -i -e 's|^(subjectAltName=)|#$1|;' /etc/ssl/openssl.cnf
WORKDIR /root
CMD ["/root/tools/run.sh"]
