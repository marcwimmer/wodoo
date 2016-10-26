cd /root/tools
./pack_server_conf.sh
./pack_client_conf.sh asterisk            internalremote.conf   notar   asterisk.conf
./pack_client_conf.sh dns                 internalremote.conf   notar   dns.conf
./pack_client_conf.sh ntp                 internalremote.conf   notar   ntp.conf
./pack_client_conf.sh client              defaultclient.conf    notar   softphone.conf
./pack_client_conf.sh server-as-client    internalremote.conf    notar   server-as-client.conf
./pack_client_conf.sh client-with-route   vpn.cnf               tar     snom.tar
./pack_client_conf.sh client-with-route50   vpn.cnf               tar     snom50.tar
./pack_client_conf.sh client-with-route51   vpn.cnf               tar     snom51.tar
./pack_client_conf.sh client-with-route52   vpn.cnf               tar     snom52.tar
./pack_client_conf.sh client-with-route53   vpn.cnf               tar     snom53.tar

