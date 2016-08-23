###
#
# DOCKER File to Create - OVPN CA Certificates for ca,server and client.
# 
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

CMD echo "Please execute the make-certs.sh to utilize this machine."

