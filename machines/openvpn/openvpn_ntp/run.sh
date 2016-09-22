#!/bin/bash
set -e
mkdir -p /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

/etc/init.d/ntp start &
openvpn /opt/certs/ntp.conf &

while true;
do
    ps aux|grep -q ntp || break
    ps aux|grep -q openvpn || break

    echo "Showing Status..."
    set +e
    ifconfig
    ntpq -p
    set -e
    sleep 2
done
