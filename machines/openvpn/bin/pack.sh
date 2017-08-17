#!/bin/bash
[[ "$VERBOSE" == "1" ]] && set -x
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
if [[ -z "$dc" ]]; then
    echo "docker-compose instruction missing"
    exit -1
fi

#create new Certificate Chain
run="$dc run ovpn_manage"

# create client keys (corresponds with name in ccd)
$run make_client_keys.sh asterisk
$run make_client_keys.sh dns
$run make_client_keys.sh ntp
$run make_client_keys.sh odoo
$run make_client_keys.sh client
$run make_client_keys.sh server-as-client

# create routed clients(phones)
if [[ -n "$PHONE_VPN_START" && -n "$PHONE_VPN_END" ]]; then
    i=$((PHONE_VPN_START))
    while $i < $((PHONE_VPN_END)); do
        CLIENT=client-$i
        $run /root/tools/make_client_keys.sh "$CLIENT"
        IP=$(python "$DIR/get_ip.py" "10.28.0.0" $i)
        i=$((i + 1))
        # enter IP
        sed -i "s|__IP__|$IP|g" "$DIR/ccd/$CLIENT"
    done
fi

# changing the openvpn config and just restarting also updates
# configurations for phones and so on
$run pack_server_conf.sh
$run pack_client_conf.sh
