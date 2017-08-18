#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh
prepare_ca_tools.sh
TMP=$(mktemp -u)
mkdir -p $TMP
cp $KEY_DIR/server.crt $TMP
cp $KEY_DIR/server.key $TMP/server.key
cp $KEY_DIR/ca.crt $TMP/ 
cp $KEY_DIR/ta.key $TMP/ta.key
cp $KEY_DIR/dh$KEY_SIZE.pem $TMP/dh$KEY_SIZE.pem
FILENAME=$TMP/server.conf
cp $PATH_CONFIG_TEMPLATES/server.conf $FILENAME

sed -i "s|__CIPHER__|${OVPN_CIPHER}|g" $FILENAME
$(
cd /usr/local/bin
export OVPN_SERVER_CONF=$FILENAME
python process_config.py
)


cd $TMP
tar -czf ../server.tgz ./*
cd ..
mv server.tgz /root/server_out/
rm -rf $TMP

