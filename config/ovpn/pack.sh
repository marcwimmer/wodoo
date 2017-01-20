#!/bin/bash
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
if [[ -z "$dc" ]]; then
    echo "docker-compose instruction missing"
    exit -1
fi

#create new Certificate Chain
runca="$dc run ovpn_ca"
runmakekeys="$dc run ovpn_makekeys"

# create client keys (corresponds with name in ccd)
$runca /root/tools/make_client_keys.sh asterisk
$runca /root/tools/make_client_keys.sh dns
$runca /root/tools/make_client_keys.sh ntp
$runca /root/tools/make_client_keys.sh odoo
$runca /root/tools/make_client_keys.sh client
$runca /root/tools/make_client_keys.sh server-as-client

# create routed clients(phones)
if [[ -n "$PHONE_VPN_START" && -n "$PHONE_VPN_END" ]]; then
    i=$((PHONE_VPN_START))
    while $i < $((PHONE_VPN_END)); do
        CLIENT=client-$i
        $runca /root/tools/make_client_keys.sh "$CLIENT"
        IP=$(python "$DIR/get_ip.py" "10.28.0.0" $i)
        i=$((i + 1))
        # enter IP
        sed -i "s|__IP__|$IP|g" "$DIR/ccd/$CLIENT"
    done
fi

# changing the openvpn config and just restarting also updates
# configurations for phones and so on
$runmakekeys /root/tools/run.sh JUSTPACK
