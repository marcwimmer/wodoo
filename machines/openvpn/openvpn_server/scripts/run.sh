#!/bin/bash

set -ex

cd /root/server_out
if [ ! -f /root/ovpn/server.conf ]; then
    if [ ! -f server.tgz ]
    then
        echo "Missing server config - please create CA and keys"
        exit -1
    fi
fi

if [ ! -d /root/ovpn ]
then
    mkdir /root/ovpn
fi


echo "Found server config! Continue..."
cp server.tgz /root/ovpn/
cd /root/ovpn
tar xzf server.tgz
rm server.tgz
cd /root/tools
echo "Installation of Certificates finished"

mkdir -p /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

echo "Starting ovpn Server"
/usr/sbin/openvpn /root/ovpn/server.conf
