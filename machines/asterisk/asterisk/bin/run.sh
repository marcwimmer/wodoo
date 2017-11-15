#!/bin/bash
set -e

if [[ "$RUN_ASTERISK" == "0" ]]; then
    echo "asterisk is turned off by settings - good bye! :)"
    exit 0
fi

#connect to openvpn server
if [[ ! -d /dev/net ]]; then
	mkdir /dev/net
fi
if [[ -f /dev/net/tun ]]; then
	mknod /dev/net/tun c 10 200  # also used for tap
fi

openvpn /opt/certs/asterisk.conf &

while true;
do
    ifconfig | grep -q tap0 && break
    sleep 1
    echo 'waiting for tap device to arrive...'
    ifconfig 
done

echo "starting reloader in 30 seconds..." && sleep 30 && /root/reloader.sh &
/usr/sbin/asterisk -vvvv -dddd 
