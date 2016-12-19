FROM ubuntu:16.04

MAINTAINER Nicolas Delaby "nicolas@ezeep.com"

# Install cups
RUN apt-get update && apt-get install cups cups-pdf whois -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Disbale some cups backend that are unusable within a container
RUN mv /usr/lib/cups/backend/parallel /usr/lib/cups/backend-available/
RUN mv /usr/lib/cups/backend/serial /usr/lib/cups/backend-available/
#RUN mv /usr/lib/cups/backend/usb /usr/lib/cups/backend-available/

ADD etc-cups /etc/cups
RUN mkdir -p /etc/cups/ssl
VOLUME /etc/cups/
VOLUME /var/log/cups
VOLUME /var/spool/cups
VOLUME /var/cache/cups

ADD etc-pam.d-cups /etc/pam.d/cups

RUN apt-get -qq update
RUN apt-get install -y wget samba-client
WORKDIR /usr/lib/cups/backend
RUN wget http://willem.engen.nl/projects/cupssmb/smbc
RUN chmod a+x smbc
RUN apt-get install -y smbclient

EXPOSE 631

ADD start_cups.sh /root/start_cups.sh
RUN chmod +x /root/start_cups.sh
CMD ["/root/start_cups.sh"]
