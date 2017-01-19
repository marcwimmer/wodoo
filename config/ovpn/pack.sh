#!/bin/bash
if [[ -z "$dc" ]]; then
    echo "docker-compose instruction missing"
    exit -1
fi

#create new Certificate Chain
runca="$dc run ovpn_ca"
runmakekeys="$dc run ovpn_makekeys"

# create client keys (correspnds with name in ccd)
$runca /root/tools/make_client_keys.sh asterisk
$runca /root/tools/make_client_keys.sh dns
$runca /root/tools/make_client_keys.sh ntp
$runca /root/tools/make_client_keys.sh odoo
$runca /root/tools/make_client_keys.sh client
$runca /root/tools/make_client_keys.sh server-as-client

if [[ -n "$CUSTOM_VPN_CLIENTS" ]]; then
    IFS=',' read -ra ARR <<< "$CUSTOM_VPN_CLIENTS"
    for i in "${ARR[@]}"; do
        $runca /root/tools/make_client_keys.sh "$i"
    done
fi

# create routed clients(phones)
if [[ -n "$PHONE_VPN_START" && -n "$PHONE_VPN_END" ]]; then
    i=$((PHONE_VPN_START))
    while $i < $((PHONE_VPN_END)); do
        $runca /root/tools/make_client_keys.sh client-with-route$i
        i=$((i + 1))
    done
fi

# changing the openvpn config and just restarting also updates
# configurations for phones and so on
$runmakekeys /root/tools/run.sh JUSTPACK
