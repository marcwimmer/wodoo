#!/bin/bash
set -ex

if [[ -z "$1" ]]; then
    echo 'name required'
    exit -1
fi

cd $KEYFOLDERROOT

echo "Build Key"
export EASY_RSA="`pwd`"
export KEY_NAME=$1 
export OPENSSL="openssl"
export PKCS11TOOL="pkcs11-tool"
export GREP="grep"
export KEY_CONFIG=`$EASY_RSA/whichopensslcnf $EASY_RSA`
export KEY_DIR="$EASY_RSA/keys"
export KEY_CN=$1  # to match CCD
./build-key $1
