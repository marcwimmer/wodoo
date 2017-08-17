#!/bin/bash

set -e
[[ "$VERBOSE" ]] && set -x

PWD=$(pwd)
echo "Extracting server config..."
TMP=$(mktemp -u)
mkdir -p $TMP
cp server.tgz $TMP
cd $TMP
tar xzf server.tgz
rm server.tgz
cd $PWD

echo "Extracting done."
echo "Creating tunnel device"
if [ ! -f /dev/net/tun ]; then
    {
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200  # also used for tap
    }
fi;


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


