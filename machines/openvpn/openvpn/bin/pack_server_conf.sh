#!/bin/bash
set -x
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh
prepare_ca_tools.sh
TMP=$(mktemp -u)
mkdir -p "$TMP"
cp "$KEY_DIR/server.crt" "$TMP"
cp "$KEY_DIR/server.key" "$TMP/server.key"
cp "$KEY_DIR/ca.crt" "$TMP/"
cp "$KEY_DIR/ta.key" "$TMP/ta.key"
cp "$KEY_DIR/dh$KEY_SIZE.pem" "$TMP/dh$KEY_SIZE.pem"
FILENAME="$TMP/server.conf"
cp "$PATH_CONFIG_TEMPLATES/server.conf" "$FILENAME"

sed -i "s|__CIPHER__|${OVPN_CIPHER}|g" "$FILENAME"

cd /usr/local/bin || exit -1
export OVPN_SERVER_CONF="$FILENAME"
set +e
python process_config.py 
set -e

cd "$TMP" || exit -1
tar -czf ../server.tgz ./*
cd ..
mv server.tgz /root/server_out/
rm -rf "$TMP"

