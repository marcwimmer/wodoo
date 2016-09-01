#!/bin/bash
set -e

cd $KEYFOLDERROOT
export EASY_RSA="`pwd`"
export KEY_NAME="odoo-vpn-srv"
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"

export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"
touch ${KEYFOLDER}/index.txt

[[ -f keys/serial ]] || echo 1000 > keys/serial

./build-key-server --batch server
