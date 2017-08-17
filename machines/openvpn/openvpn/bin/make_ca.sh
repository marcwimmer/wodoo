#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
export EASY_RSA=$KEYFOLDER_ROOT
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"

export KEY_NAME="odoo-VPN"
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"


make-cadir /root/openvpn-ca-tmpl && \
rsync /root/openvpn-ca-tmpl/ /root/openvpn-ca/ -arL
cd "$KEYFOLDER_ROOT"
./build-ca  --batch --sign
./build-dh  --batch --sign
openvpn --genkey --secret $KEYFOLDER/ta.key 
rm -Rf /root/transfer/ca || true
mkdir -p /root/transfer/ca/{pub,prv}
cp keys/ca.key /root/transfer/ca/prv
cp keys/ca.crt /root/transfer/ca/pub 
tar -czf /root/transfer/ca.tgz /root/transfer/ca
rm -rf /root/transfer/ca 

echo "Please find your ca-cert/key at ./ca.tgz"
echo "finished."


make_server_keys.sh
make_default_keys.sh
pack_server_conf.sh
