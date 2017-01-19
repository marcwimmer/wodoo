#!/bin/bash
set -e
rsync /root/openvpn-ca-tmpl/ /root/openvpn-ca/ -arPL
cd "$KEYFOLDERROOT"
export EASY_RSA="`pwd`"
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"

export KEY_NAME="odoo-VPN"
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"


./build-ca  --batch --sign
./build-dh  --batch --sign
openvpn --genkey --secret $KEYFOLDER/ta.key 
mkdir /root/transfer/ca 
mkdir /root/transfer/ca/pub 
mkdir /root/transfer/ca/prv 
cp keys/ca.key /root/transfer/ca/prv
cp keys/ca.crt /root/transfer/ca/pub 
tar -czf /root/transfer/ca.tgz /root/transfer/ca
rm -rf /root/transfer/ca 

echo "Please find your ca-cert/key at ./ca.tgz"
echo "finished."






