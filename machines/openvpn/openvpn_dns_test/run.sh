#!/bin/bash
set -e

mkdir -p /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

openvpn /opt/certs/softphone.conf &
while true;
do
    ifconfig |grep -q tap0 && break
    sleep 1
done

echo "nameserver 10.28.0.3" > /etc/resolv.conf
cat /etc/resolv.conf
set -x

nslookup asterisk
nslookup asterisk |grep -q 10.28.0.2 || exit -1
nslookup 0.ntp.pool.org
nslookup 0.ntp.pool.org | grep -q 10.28.0.6 || exit -1
nslookup www.gmx.de 
dig 0.ntp.pool.org

echo 'tests succesfully done'
