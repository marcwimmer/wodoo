#!/bin/bash
set -x
CONF_ROOT=/opt/printer_setup
if [[ -d $CONF_ROOT/deb ]]; then
    cd $CONF_ROOT/deb
    for debfile in $(ls $CONF_ROOT/deb) ; do
        # dell packages crashes passwords in cups? why?....
        dpkg -i $debfile
    done
fi

rsync /opt/printer_setup/ /etc/cups -ra

# samba printing auth
PRINTAUTH=/etc/samba/printing.auth
echo "username = $CUPS_DOMAIN_USER" > $PRINTAUTH
echo "password = $CUPS_DOMAIN_PASSWORD" >> $PRINTAUTH
echo "domain = $CUPS_DOMAIN" >> $PRINTAUTH
cp /etc/samba/printing.auth /etc/cups

set -e
if [ $(grep -ci $CUPS_USER_ADMIN /etc/shadow) -eq 0 ]; then
    useradd $CUPS_USER_ADMIN --system -G root,lpadmin --no-create-home --password $(mkpasswd $CUPS_USER_PASSWORD)
fi

rsync $CONF_ROOT/ppd/ /etc/cups/ppd/ -ar
rsync $CONF_ROOT/printers.conf /etc/cups/

sleep 10 && python /print.py $WATCHPATH &

exec /usr/sbin/cupsd -f
