#!/bin/sh
set -x

cp /opt/cups_etc/* /etc/cups -r
cp /opt/cups_etc/printing.auth /etc/samba

set -e

if [ $(grep -ci $CUPS_USER_ADMIN /etc/shadow) -eq 0 ]; then
    useradd $CUPS_USER_ADMIN --system -G root,lpadmin --no-create-home --password $(mkpasswd $CUPS_USER_PASSWORD)
fi

python /print.py $WATCHPATH &

exec /usr/sbin/cupsd -f
