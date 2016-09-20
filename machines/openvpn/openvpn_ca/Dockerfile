###
# DOCKER File to Create - OVPN CA Certificate Stuff.
###
FROM ubuntu:16.04
MAINTAINER daniel.petermeier@conpower.de
RUN apt-get update && apt-get upgrade -y && apt-get install -y openvpn easy-rsa python3
EXPOSE 8080
RUN mkdir /root/server_out
RUN mkdir /root/tools
RUN mkdir /root/client_out
RUN make-cadir /root/openvpn-ca
WORKDIR /root/client_out
ADD ./scripts/* /root/tools/
RUN chmod a+x /root/tools/*.sh
VOLUME /root/server_out
VOLUME /root/client_out
#RUN  sh ./init.sh
CMD echo "Please connect to this virtual machine and execute /root/transfer/init.sh"
