###
# DOCKER File to Create - OVPN CA Certificate Stuff.
###
FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get upgrade -y && apt-get install -y openvpn easy-rsa python3 rsync
ADD ./scripts/* /root/tools/
RUN \
mkdir -p /root/tools && \
make-cadir /root/openvpn-ca-tmpl && \
chmod a+x /root/tools/*.sh
CMD echo "Please connect to this virtual machine and execute /root/transfer/init.sh"
