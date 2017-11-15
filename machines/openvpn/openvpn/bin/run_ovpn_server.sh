#!/bin/bash

set -x
set -e
[[ "$VERBOSE" ]] && set -x

ARGS=( "$@" )
# asterisk as one word, @ as separate words
echo "${ARGS[*]}" |grep -P -q '[-]pack_server_conf' && {
	/usr/local/bin/pack_server_conf.sh
}
PWD=$(pwd)
echo "Extracting server config..."
TMP=$(mktemp -u)
mkdir -p "$TMP"
cp "$SERVER_OUT/server.tgz" "$TMP"
cd "$TMP"
tar xzf server.tgz
rm server.tgz
cd "$PWD"

echo "Extracting done."

echo "Creating tunnel device"
if [ ! -f /dev/net/tun ]; then
    {
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200  # also used for tap
    }
fi;

echo "Starting ovpn Server"
/usr/sbin/openvpn "$TMP/server.conf"
