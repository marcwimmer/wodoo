#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh

if [[ $(find $KEY_DIR -name server.key) ]]; then
	echo "Server key already created - aborting"
	exit -1
fi

export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_NAME="server-${VPN_DOMAIN}"
prepare_ca_tools.sh
touch ${KEY_DIR}/index.txt

[[ -f $KEY_DIR/serial ]] || echo $OVPN_SERIAL_START > $KEY_DIR/serial

cd $EASY_RSA
./build-key-server --batch server

cd /usr/local/bin
python process_config.py
