FROM debian:stretch

MAINTAINER Nicolas Delaby "nicolas@ezeep.com"

# Install cups
RUN apt-get update && apt-get install cups cups-pdf whois wget samba-client python3 python3-cups rsync python3-pip vim -y \
&& apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN pip3 install pip --upgrade
RUN pip3 install pathlib

# Disbale some cups backend that are unusable within a container
RUN mv /usr/lib/cups/backend/parallel /usr/lib/cups/backend-available/
RUN mv /usr/lib/cups/backend/serial /usr/lib/cups/backend-available/
#RUN mv /usr/lib/cups/backend/usb /usr/lib/cups/backend-available/

ADD etc-cups/ /etc/cups.template/
VOLUME /var/spool/cups
VOLUME /var/cache/cups

ADD etc-pam.d-cups /etc/pam.d/cups
ADD print.py /print.py
RUN chmod a+x /print.py

ADD smbc /usr/lib/cups/backend/smbc
RUN chmod a+x /usr/lib/cups/backend/smbc

EXPOSE 631

ADD backup_printers.sh /backup_printers.sh
RUN chmod a+x /backup_printers.sh

ADD start_cups.sh /root/start_cups.sh
RUN chmod +x /root/start_cups.sh
CMD ["/root/start_cups.sh"]

# Trigger initial apply of configs; you can also map the /etc/cups directory to your own folder
RUN rm -Rf /etc/cups/cupsd.conf
RUN ls /etc/cups -lhtra
