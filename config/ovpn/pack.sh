#!/bin/bash

if [[ "$1" == 'keys' ]]; then
    #create new Certificate Chain
    $dc run ovpnca /root/tools/clean_keys.sh
    $dc run ovpnca /root/tools/init.sh
    $dc run ovpnca /root/tools/make_server_keys.sh

    # create client keys (correspnds with name in ccd)
    $dc run ovpnca /root/tools/make_client_keys.sh asterisk
    $dc run ovpnca /root/tools/make_client_keys.sh dns
    $dc run ovpnca /root/tools/make_client_keys.sh ntp
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route
   
    # create routed clients(phones)

    # for loop requires CLIENT_START and CLIENT_END variables in environment
    #for c in `seq $CLIENT_START $CLIENT_END`;
    #do
#	$dc run ovpnca /root/tools/make_client_keys.sh client-with-route$c
    #done
    # TODO: Generate matching IP's and generate ccd,
    #       then client generation can be controlled by env

    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route51
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route52
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route53
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route54
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route55
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route56
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route57
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route58
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route59
    $dc run ovpnca /root/tools/make_client_keys.sh client-with-route60
    $dc run ovpnca /root/tools/make_client_keys.sh client
    $dc run ovpnca /root/tools/make_client_keys.sh server-as-client

    # changing the openvpn config and just restarting also updates
    # configurations for phones and so on
    $dc run ovpn_makekeys /root/tools/run.sh JUSTPACK

else

    cd /root/tools
    ./pack_server_conf.sh
    ./pack_client_conf.sh asterisk            internalremote.conf   notar   asterisk.conf
    ./pack_client_conf.sh dns                 internalremote.conf   notar   dns.conf
    ./pack_client_conf.sh ntp                 internalremote.conf   notar   ntp.conf
    ./pack_client_conf.sh client              defaultclient.conf    notar   softphone.conf
    ./pack_client_conf.sh server-as-client    internalremote.conf    notar   server-as-client.conf

    # packing clients with for loop requires START and END variables in env
    #for c in `seq $CLIENT_START $CLIENT_END`;
    #do
    #./pack_client_conf.sh client-with-route$c   vpn.cnf               tar     snom$c.tar
    #done
    # TODO: Generate matching IP's and generate ccd,
    #       then client generation can be controlled by env


    ./pack_client_conf.sh client-with-route   vpn.cnf               tar     snom.tar
    ./pack_client_conf.sh client-with-route50   vpn.cnf               tar     snom50.tar
    ./pack_client_conf.sh client-with-route51   vpn.cnf               tar     snom51.tar
    ./pack_client_conf.sh client-with-route52   vpn.cnf               tar     snom52.tar
    ./pack_client_conf.sh client-with-route53   vpn.cnf               tar     snom53.tar
    ./pack_client_conf.sh client-with-route54   vpn.cnf               tar     snom54.tar
    ./pack_client_conf.sh client-with-route55   vpn.cnf               tar     snom55.tar
    ./pack_client_conf.sh client-with-route56   vpn.cnf               tar     snom56.tar
    ./pack_client_conf.sh client-with-route57   vpn.cnf               tar     snom57.tar
    ./pack_client_conf.sh client-with-route58   vpn.cnf               tar     snom58.tar
    ./pack_client_conf.sh client-with-route59   vpn.cnf               tar     snom59.tar
    ./pack_client_conf.sh client-with-route60   vpn.cnf               tar     snom60.tar

fi
