#!/bin/bash
set -e
set -x

# if not then you can debug on ari the stasis
if [[ "$RUN_STASIS_ON_ASTERISK" == "1" ]]; then
    # clone latest stasis application from deploy branck
    [[ -d /opt/asterisk_ari ]] && rm -Rf /opt/asterisk_ari
    git clone git.mt-software.de:/git/openerp/modules/asterisk_ari --branch deploy --single-branch /opt/asterisk_ari
    cd /opt/asterisk_ari
    git checkout deploy -f
fi

#connect to openvpn server
mkdir /dev/net
mknod /dev/net/tun c 10 200  # also used for tap

openvpn /opt/certs/asterisk.conf &
while true;
do
    ifconfig | grep -q tap0 && break
    sleep 1
    echo 'waiting for tap device to arrive...'
    ifconfig 
done

echo "starting reloader in 30 seconds..." && sleep 30 && /root/reloader.sh &
/usr/sbin/asterisk -vvvv -dddd
