#!/bin/bash
set +x

if [[ -z "$WATCHPATH" ]]; then
	echo "Please define WATCHPATH!"
	exit -1
fi

if [[ -z "$CUPS_USER_ADMIN" || -z "$CUPS_USER_PASSWORD" ]]; then
	echo "Please define CUPS_USER_ADMIN and CUPS_USER_PASSWORD!"
	exit -1
fi

echo "setting ownership of $WATCHPATH to odoo"
chown "$DEFAULT_USER":"$DEFAULT_USER" "$WATCHPATH" -R
echo "setting ownership of $WATCHPATH to odoo done!"

CONF_ROOT=/opt/printer_setup
if [[ -d $CONF_ROOT/deb ]]; then
    cd $CONF_ROOT/deb
    for debfile in $(ls $CONF_ROOT/deb) ; do
        # dell packages crashes passwords in cups? why?....
        dpkg -i "$debfile"
    done
fi

rsync /opt/printer_setup/ /etc/cups -ra
rsync /etc/cups.template/ /etc/cups/ -arP
mkdir -p /etc/cups/ssl

# samba printing auth
PRINTAUTH=/etc/samba/printing.auth
echo "username = $CUPS_DOMAIN_USER" > $PRINTAUTH
echo "password = $CUPS_DOMAIN_PASSWORD" >> $PRINTAUTH
echo "domain = $CUPS_DOMAIN" >> $PRINTAUTH
cp /etc/samba/printing.auth /etc/cups

set -e
if [ "$(grep -ci "$CUPS_USER_ADMIN" /etc/shadow)" -eq 0 ]; then
    useradd "$CUPS_USER_ADMIN" --system -G root,lpadmin --no-create-home --password "$(mkpasswd "$CUPS_USER_PASSWORD")"
fi

rsync $CONF_ROOT/ /etc/cups/ -ar

sleep 10 && python3 /print.py "$WATCHPATH" "$PRINTED_PATH" &
sleep 5 && /backup_printers.sh &

openssl req -new -x509 -keyout /etc/cups/ssl/server.key -out /etc/cups/ssl/server.crt -days 365 -nodes -subj "/C=NL/ST=Zuid Holland/L=Rotterdam/O=Sparkling Network/OU=IT Department/CN=ssl.raymii.org" || true
exec /usr/sbin/cupsd -f
