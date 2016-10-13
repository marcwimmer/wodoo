FROM ubuntu:14.04
MAINTAINER Marc Wimmer

# Packages
RUN apt-get update --fix-missing
RUN apt-get -y upgrade
# procmail sets up mailbox directories; postconf |grep mailbox_command
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install vim postfix dovecot-core dovecot-imapd telnet supervisor postfix-pcre procmail mailutils
RUN apt-get autoclean && rm -rf /var/lib/apt/lists/*

ADD etc/ etc/

ADD install.sh /install.sh
RUN chmod a+x /install.sh
RUN /install.sh

ADD testmail.sh /test.sh
RUN chmod a+x /test.sh

# Start-mailserver script
ADD run /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
