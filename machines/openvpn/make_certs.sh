#!/bin/bash
set -e

echo "Please enter many enters :)"
docker-compose run ovpn_ca /root/tools/clean_keys.sh
docker-compose run ovpn_ca /root/tools/init.sh
docker-compose run ovpn_ca /root/tools/make_server_keys.sh

docker-compose run ovpn_ca /root/tools/make_client_keys.sh asterisk

# TODO check name in conf client.key
docker-compose run ovpn_ca /root/tools/make_client_keys.sh CLIENT
