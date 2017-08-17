#!/bin/bash

set -e
set -x

cd /root/server_out
if [ ! -f /root/openvpn-ca/keys/ca.crt ]; then
    echo "Missing CA - please create CA and keys"
    exit -1
fi

mkdir -p /root/ovpn
mkdir -p /root/confs
cp /root/input/confs/* /root/confs/ -R
