#!/bin/bash

###
# 
# Starts an ovpn client, so that scanning of existing phones can take place.
#
###

set -e
[[ "$VERBOSE" ]] && set -x

echo "Creating tunnel device"
if [ ! -f /dev/net/tun ]; then
    {
    mkdir -p /dev/net
    mknod /dev/net/tun c 10 200  # also used for tap
    }
fi;


echo "Starting ovpn Server-Client"
/usr/sbin/openvpn $CLIENT_OUT/${OVPN_DOMAIN}_ovpn_server
