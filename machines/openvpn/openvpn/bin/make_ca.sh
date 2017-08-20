#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x

if [ -f $KEY_DIR/ca.crt ]; then
	echo "Please clean existing CA before. (Using clean_all.sh)"
	exit -1
fi

prepare_ca_tools.sh
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_NAME="CA-$OVPN_DOMAIN"

cd "$EASY_RSA"
./build-ca  --batch --sign
./build-dh  --batch --sign
sync # otherwise the ca.key file is not written
openvpn --genkey --secret $KEY_DIR/ta.key 
TMP=$(mktemp -u)
mkdir -p $TMP
mkdir -p $TMP/ca/{pub,prv}
cp $KEY_DIR/ca.key $TMP/ca/prv
cp $KEY_DIR/ca.crt $TMP/ca/pub 
tar -czf /root/CA/ca.tgz $TMP/ca
rm -Rf $TMP

echo "Please find your ca-cert/key at ./ca.tgz"
echo "finished."

make_server_keys.sh
make_default_keys.sh
pack_server_conf.sh
