#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh
cd $KEYFOLDER_ROOT
TMP=$(mktemp -u)
mkdir -p $TMP
cp $KEYFOLDER/server.crt $TMP
cp $KEYFOLDER/server.key $TMP/server.key
cp $KEYFOLDER/ca.crt $TMP/ 
cp $KEYFOLDER/ta.key $TMP/ta.key
cp $KEYFOLDER/dh$KEY_SIZE.pem $TMP/dh$KEY_SIZE.pem
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

