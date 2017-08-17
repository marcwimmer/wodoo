###
# DOCKER File to Create and manage openvpn
###
FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get upgrade -y && apt-get install -y openvpn easy-rsa python3 rsync
ADD bin/* /usr/local/bin/
RUN \
make-cadir /root/openvpn-ca-tmpl && \
chmod a+x /usr/local/bin/*.sh
CMD echo "Please connect to this virtual machine and execute /root/transfer/init.sh"
