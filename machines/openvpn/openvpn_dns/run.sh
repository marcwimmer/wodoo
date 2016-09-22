#!/bin/bash
set -e

mkdir -p /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

openvpn /opt/certs/dns.conf &

while true;
do
    ifconfig | grep -q tap0 && break
    sleep 1
    echo "Waiting for tap device"
done

echo "ENABLED=1" > /etc/default/dnsmasq

/etc/init.d/dnsmasq start &

while true;
do
    ps aux | grep -q dnsmasq || break
	sleep 1
done
