#!/bin/bash
set -e
[[ "$VERBOSE" == "1" ]] && set -x
check_has_ca.sh

export EASY_RSA=$KEYFOLDER_ROOT
export KEY_NAME="odoo-vpn-srv"
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"

export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"
touch ${KEYFOLDER}/index.txt

cd $KEYFOLDER_ROOT
[[ -f keys/serial ]] || echo 1000 > keys/serial

./build-key-server --batch server

cd /usr/local/bin
python process_config.py
