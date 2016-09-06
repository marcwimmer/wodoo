#!/bin/bash
set -e

docker-compose run ovpnca /root/tools/clean_keys.sh
docker-compose run ovpnca /root/tools/init.sh
docker-compose run ovpnca /root/tools/make_server_keys.sh

docker-compose run ovpnca /root/tools/make_client_keys.sh asterisk

# TODO check name in conf client.key
docker-compose run ovpnca /root/tools/make_client_keys.sh CLIENT

# pack client scripts together
docker-compose run ovpn-server /root/tools/pack_server_conf.sh
docker-compose run ovpn-server /root/tools/pack_client_conf.sh asterisk asterisk.conf notar asterisk.conf
docker-compose run ovpn-server /root/tools/pack_client_conf.sh CLIENT vpn.cnf tar snom.tar
docker-compose run ovpn-server /root/tools/pack_client_conf.sh CLIENT softphone.conf notar softphone.conf 

