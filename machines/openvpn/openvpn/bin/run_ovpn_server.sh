#!/bin/bash

set -e
[[ "$VERBOSE" ]] && set -x
set -x

just_pack.sh


echo "Found server config! Continue..."
cp server.tgz /root/ovpn/
cd /root/ovpn
tar xzf server.tgz
rm server.tgz
cd /root/tools
echo "Installation of Certificates finished"
if [ ! -f /dev/net/tun ]; then
    {
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200  # also used for tap
    }
fi;

# replace vars in ccd
mkdir -p /root/ccd
cp /tmp/ccd/* /root/ccd/
find /root/ccd -type f -exec sed -i "s/__CLIENT_NET__/$CLIENT_NET/g" {} \;
find /root/ccd -type f -exec sed -i "s/__CLIENT_NETMASK__/$CLIENT_NETMASK__/g" {} \;


echo "showing available ciphers"
/usr/sbin/openvpn --show-ciphers

echo "Starting ovpn Server"
/usr/sbin/openvpn /root/ovpn/server.conf &
PID_SERVER=$!
echo $PID_SERVER > /run/pid
/usr/sbin/openvpn /root/client_out/server-as-client.conf &
PID_SERVERASCLIENT=$!
/root/tools/scan_clients.sh &

while true;
do
    ps -o pid |grep -q $PID_SERVER || {
        echo "openvpn server down - tearing down"
        break
    }
    ps -o pid |grep -q $PID_SERVERASCLIENT || {
        echo "openvpn client down - tearing down"
        break
    }
    sleep 2
done


