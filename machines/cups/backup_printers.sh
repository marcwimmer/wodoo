#!/bin/bash

# CUPS sometimes (dont know when) makes a printers.conf.N file (containing all the setup).
# store the latest printers.conf at the original place.

while true;
do
	
	cd /etc/cups || exit -1
	latest_file="$(ls -lta|grep printers.conf |head -n1| awk '{print $(NF-0)}')"

	rsync "$latest_file" "$CONF_ROOT/printers.conf"

	sleep 1
done
