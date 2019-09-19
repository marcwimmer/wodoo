FROM debian:buster
MAINTAINER Marc Wimmer

# Packages
RUN apt-get update --fix-missing
RUN apt-get -y upgrade
# procmail sets up mailbox directories; postconf |grep mailbox_command
RUN DEBIAN_FRONTEND=noninteractive apt-get -y install vim postfix dovecot-core dovecot-imapd telnet postfix-pcre procmail mailutils rsyslog
RUN apt-get autoclean && rm -rf /var/lib/apt/lists/*

ADD etc/ etc/

ADD install.sh /install.sh
RUN chmod a+x /install.sh
RUN /install.sh

# Start-mailserver script
ADD run.sh /run.sh
RUN chmod a+x /run.sh

ADD sslsettings.txt .
# Generate a root private key (rootCA.key):
RUN openssl genrsa -out rootCA.key 2048
# Generate a self-singed root certificate (rootCA.pem):
RUN cat sslsettings.txt | openssl req -x509 -new -nodes -key rootCA.key -days 1024 -out rootCA.pem
# Create a private key for the final certificate (dovecot.key):
RUN openssl genrsa -out dovecot.key 2048
# Create a certificate sign request (dovecot.csr):
RUN cat sslsettings.txt | openssl req -new -key dovecot.key -out dovecot.csr

# Create a certificate based on the root CA certificate and the root private key (dovecot.crt):
RUN openssl x509 -req -in dovecot.csr -CA rootCA.pem -CAkey rootCA.key -CAcreateserial -out dovecot.crt -days 500
# Copy the private key and the certificate to the /etc/dovecot/private/ directory
RUN cp dovecot.crt /etc/dovecot/private/dovecot.crt && \
cp dovecot.key /etc/dovecot/private/dovecot.key && \
chmod 400 /etc/dovecot/private/dovecot.crt && \
chmod 400 /etc/dovecot/private/dovecot.key



CMD ["/run.sh"]
