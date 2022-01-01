#!/bin/bash

# CUPS sometimes (dont know when) makes a printers.conf.N file (containing all the setup).
# store the latest printers.conf at the original place.

while true;
do
	
	cd /etc/cups || exit -1
	latest_file="$(ls -lta|grep printers.conf |head -n1| awk '{print $(NF-0)}')"

    if [[ -f "$latest_file" ]]; then
        rsync "$latest_file" "$CONF_ROOT/printers.conf"
        rsync /etc/cups/ppd "$CONF_ROOT/" -ar --delete-after
    fi

	sleep 1
done
