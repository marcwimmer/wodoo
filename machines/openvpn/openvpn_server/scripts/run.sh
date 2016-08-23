#!/bin/bash

set -ex

# pack client scripts together
/root/tools/pack_server_conf.sh
/root/tools/pack_client_conf.sh "asterisk"
/root/tools/pack_client_conf.sh "CLIENT"

cd /root/server_out
# check if server configuration exists
if [ ! -f /root/ovpn/server.conf ]; then
    if [ ! -f server.tgz ]
    then
        echo "Missing server config - please create CA and keys"
        exit -1
    fi
fi
# if local configuration directory doesn't exist, create it
if [ ! -d /root/ovpn ]
then
    mkdir /root/ovpn
fi

# certificate installation procedure
echo "Found server config! Installing certificates ..."
cp server.tgz /root/ovpn/
cd /root/ovpn
tar xzf server.tgz
rm server.tgz
cd /root/tools
echo "... done, Installation of certificates finished"

# create tunnel device for vpn
mkdir -p /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

# start openvpnserver with not default config
echo "Starting ovpn Server"
/usr/sbin/openvpn /root/ovpn/server.conf
